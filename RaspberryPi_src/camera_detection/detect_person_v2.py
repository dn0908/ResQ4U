import sys
sys.path.append('/home/roboin/ResQ4U/RaspberryPi_src/common')
from imports import *
#  

class PersonDetector:
    def __init__(self, pan_tilt, show_image=True, record_vid=False ):
        self.show_image = show_image

        # Flag for detection start
        self.is_detected = False
        self.detection_start_flag = False
        self.tracking = False
        self.count = 0

        # Initialize bounding box centder point
        self.xc = 0
        self.yc = 0
        
        # Set input image frame size to 1080p FULL HD
        self.width  = 1920
        self.height = 1080

        # # # Set input image frame size to 720p HD
        # self.width  = 1280
        # self.height =  720
        
        # Set input image frame size to 480p HD
        # self.width  = 640
        # self.height = 480

        self.framerate = 10 #fps

        self.crop_size = 350
        self.cropped_im_center = [0, 0]

        # 1080p
        self.sliding_idx_x = 7
        self.sliding_idx_y = 6

        # self.sliding_idx_x = 5
        # self.sliding_idx_y = 4

        self.sliding_pixel_x = int((self.width - self.crop_size) / (self.sliding_idx_x - 1))
        self.sliding_pixel_y = int((self.height - self.crop_size) / (self.sliding_idx_y - 1))

        self.align_offset = 10
        
        self.i = 0
        self.j = 0

        self.pan_tilt = pan_tilt

        default_model_dir = '/home/roboin/ResQ4U/RaspberryPi_src/all_models/'
        default_model = 'mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite'
        default_labels = 'coco_labels.txt'
        
        parser = argparse.ArgumentParser()
        parser.add_argument('--model', help='.tflite model path',
                            default=os.path.join(default_model_dir,default_model))
        parser.add_argument('--labels', help='label file path',
                            default=os.path.join(default_model_dir, default_labels))
        parser.add_argument('--top_k', type=int, default=3,
                            help='number of categories with highest score to display')
        parser.add_argument('--camera_idx', type=int, help='Index of which video source to use. ', default = 0)
        parser.add_argument('--threshold', type=float, default=0.5,
                            help='classifier score threshold')
        self.args = parser.parse_args()

        print('Loading {} with {} labels.'.format(self.args.model, self.args.labels))
        self.interpreter = make_interpreter(self.args.model)
        self.interpreter.allocate_tensors()
        self.labels = read_label_file(self.args.labels)
        self.inference_size = input_size(self.interpreter)

        self.cap = cv2.VideoCapture(self.args.camera_idx, cv2.CAP_V4L)
        # self.cap = cv2.VideoCapture('/dev/vidoe0', cv2.CAP_V4L)

        width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print('* original frame size setting: width=%d, height=%d' % (width, height))
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        width_stream = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height_stream = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print('** set streaming frame size to: width=%d, height=%d' % (width_stream, height_stream))
        print('streaming set done')
        
        self.cap.set(cv2.CAP_PROP_FPS, self.framerate)
        print(f'fps set to {self.framerate}')

        self.record_vid = record_vid

        if self.record_vid:
            # video writer
            fourcc = cv2.VideoWriter_fourcc(*'DIVX')
            save_dir = 'output_' + str(time.time()) + '.avi'
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.writer = cv2.VideoWriter(save_dir, fourcc, fps-1, (self.width, self.height))
            
            if not self.writer.isOpened():
                print("File open failed")
                sys.exit()

    def detect(self):
        
        # try:
        while self.cap.isOpened():
            ret, frame = self.cap.read()

            if not ret:
                print('ret frame NONE')
                break

            # Visualize grid
            cv2_im = cv2.line(frame, (int(self.width / 2), 0), (int(self.width / 2), self.height), (255,255,255), 1)
            cv2_im = cv2.line(frame, (0, int(self.height / 2)), (self.width, int(self.height / 2)), (255,255,255), 1)
            cv2_im = cv2.line(frame, (0, int(self.height / 2) + self.align_offset), (self.width, int(self.height / 2) + self.align_offset), (255,255,255), 1)

            if self.j < self.sliding_idx_y - 1:
                if self.i < self.sliding_idx_x - 1:
                    self.i += 1
                else:
                    self.i = 0
                    self.j += 1
            else:
                if self.i < self.sliding_idx_x - 1:
                    self.i += 1
                else:
                    self.i = 0
                    self.j = 0

            # Crop image
            if (self.tracking == True):
                self.cropped_im_center[0] = max(min(self.xc, self.width - int(self.crop_size / 2)), int(self.crop_size / 2))
                self.cropped_im_center[1] = max(min(self.yc, self.height - int(self.crop_size / 2)), int(self.crop_size / 2))
            else:
                self.cropped_im_center = [int(self.crop_size / 2 + self.sliding_pixel_x * self.i), int(self.crop_size / 2 + self.sliding_pixel_y * self.j)]
            y1 = self.cropped_im_center[1] - int(self.crop_size / 2)
            y2 = self.cropped_im_center[1] + int(self.crop_size / 2)
            x1 = self.cropped_im_center[0] - int(self.crop_size / 2)
            x2 = self.cropped_im_center[0] + int(self.crop_size / 2)

            cv2_im = frame[y1:y2, x1:x2]

            cv2_im_rgb = cv2.cvtColor(cv2_im, cv2.COLOR_BGR2RGB)
            cv2_im_rgb = cv2.resize(cv2_im_rgb, self.inference_size)
            run_inference(self.interpreter, cv2_im_rgb.tobytes())
            objs = get_objects(self.interpreter, self.args.threshold)[:self.args.top_k]
            cv2_im = self.append_objs_to_img(cv2_im, self.inference_size, objs, self.labels)
            cv2_im = cv2.rectangle(cv2_im, (0, 0), (self.crop_size, self.crop_size), (0, 0, 255), 2)

            if self.is_detected and self.detection_start_flag == False:
                print("0")
                self.detection_start_flag = True
                return 0

            if self.is_detected:
                self.pan_tilt.pan_tilt([self.xc, self.yc])
                if self.pan_tilt.align_flag == True:
                    self.cap.release()
                    cv2.destroyAllWindows()
                    print("1")
                    return 1

            if self.record_vid:
                self.writer.write(frame)

            cv2.imshow('frame', frame)
            if cv2.waitKey(round(1000/self.framerate)) == 27 & 0xFF == ord('q'):
                break
            # if self.show_image == True:
            #     cv2.imshow('frame', frame)
            #     if cv2.waitKey(1) & 0xFF == ord('q'):
            #         break
                        
        # except Exception as e:
        #     # Handle any other exceptions that might occur
        #     print("Error occurred while streaming video :", str(e))
            
        # finally:
            # Release the video capture and close any open windows
        self.cap.release()
        self.writer.release()
        cv2.destroyAllWindows()

    def append_objs_to_img(self, cv2_im, inference_size, objs, labels):
        height, width, channels = cv2_im.shape
        scale_x, scale_y = width / inference_size[0], height / inference_size[1]
        self.is_detected = False
            
        for obj in objs:
                
            if labels[obj.id] == 'person':
                self.count = 0
                self.is_detected = True
                bbox = obj.bbox.scale(scale_x, scale_y)
                x0, y0 = int(bbox.xmin), int(bbox.ymin)
                x1, y1 = int(bbox.xmax), int(bbox.ymax)

                self.xc = self.cropped_im_center[0] - int(self.crop_size / 2) + int((x0+x1)/2)
                self.yc = self.cropped_im_center[1] - int(self.crop_size / 2) + int((y0+y1)/2)
                #print(self.xc, self.yc)

                percent = int(100 * obj.score)

                label = '{}% {}'.format(percent, labels.get(obj.id, obj.id))
                cv2_im = cv2.rectangle(cv2_im, (x0, y0), (x1, y1), (0, 255, 0), 2)
                cv2_im = cv2.putText(cv2_im, label, (x0, y0+30),
                                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
                cv2_im = cv2.circle(cv2_im, (int((x0+x1)/2), int((y0+y1)/2)), 3, (255,255,255), -1)
        
        if (self.is_detected == True):
            self.count = 0
            self.tracking = True
        else:
            self.count += 1
            if (self.count > 20):
                self.tracking = False
                self.count = 0

        return cv2_im



# if __name__ == '__main__':
#     detector = PersonDetector()
#     detector.detect()
