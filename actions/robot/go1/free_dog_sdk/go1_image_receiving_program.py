import cv2
# print(cv2.getBuildInformation())

class camera:
    def __init__(self, cam_id = None, width = 640, height = 480):
        self.width = 640
        self.cam_id = cam_id
        self.width = width
        self.height = height
    def get_img(self):
        # https://github.com/unitreerobotics/UnitreecameraSDK/issues/12 
        # IpLastSegment = "161"
        IpLastSegment = "52"
        # IpLastSegment = "15"
        # IpLastSegment = "13"
        cam = self.cam_id
        udpstrPrevData = "udpsrc address=192.168.123."+ IpLastSegment + " port="
        udpPORT = [9201,9202,9203,9204,9205]
        # https://stackoverflow.com/questions/77446163/gstreamer-gstreamer-cant-find-avdec-h264-brew-cant-install-gst-libav-anymore 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! queue ! appsink"
        # https://gstreamer.freedesktop.org/documentation/applemedia/vtdec.html?gi-language=c#vtdec 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! autovideosink sync=false"
        # https://stackoverflow.com/questions/52879501/using-gstreamer-with-python-opencv-to-capture-live-stream 
        # https://stackoverflow.com/questions/69137752/gstreamer-appsink-is-much-more-slower-than-filesink 
        # appsink syncs to the clock 
        # when you use appsink the buffers will be synchronized to the pipeline clock - this will make your pipeline run in real-time (and not faster) 
        udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! appsink drop=1" # works 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! vtdec ! videoconvert ! appsink drop=1" # works 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! vtdec_hw ! videoconvert ! appsink drop=1" # works 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! appsink" # works 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! appsink sync=false" # works
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! appsink drop=1 sync=false" # works

        # https://gstreamer.freedesktop.org/documentation/opencv/cvtracker.html?gi-language=c 
        # udpstrBehindData = " ! application/x-rtp,media=video,encoding-name=H264 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! cvtracker box-x=50 box-y=50 box-wdith=50 box-height=50 ! videoconvert ! appsink drop=1" 

        udpSendIntegratedPipe_0 = udpstrPrevData +  str(udpPORT[cam-1]) + udpstrBehindData
        # udpSendIntegratedPipe_0 = 'udpsrc address=192.168.123.52 port=9201 caps = "application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string)H264, payload=(int)96" ! rtph264depay ! decodebin ! videoconvert ! appsink'
        print(udpSendIntegratedPipe_0)        

        self.cap = cv2.VideoCapture(udpSendIntegratedPipe_0, cv2.CAP_GSTREAMER)
        # self.cap = cv2.VideoCapture(udpSendIntegratedPipe_0)

        if not self.cap.isOpened():
            raise Exception("Could not open video device")

    def demo(self):
        self.get_img()    
        while(True):
            self.ret, self.frame = self.cap.read()
            # print(f"ret: {self.ret}, frame: {self.frame}")
            if self.frame is None:
                break
            self.frame = cv2.resize(self.frame, (self.width, self.height))
            if self.cam_id == 1:
                self.frame = cv2.flip(self.frame, -1)
            if self.frame is not None:
                cv2.imshow("video0", self.frame)
            if cv2.waitKey(2) & 0xFF == ord('q'):
                break
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    cam = camera(1)
    cam.demo()