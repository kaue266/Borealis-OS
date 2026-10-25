// Real backlight HAL for the installed A30 panel. No fabricated light devices.
#include <aidl/android/hardware/light/BnLights.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android/log.h>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
using namespace aidl::android::hardware::light;
static constexpr const char* kBrightness="/sys/class/backlight/panel/brightness";
static constexpr const char* kMaximum="/sys/class/backlight/panel/max_brightness";
class A30Lights final : public BnLights {
 public:
  ndk::ScopedAStatus getLights(std::vector<HwLight>* result) override {
    HwLight light; light.id=0; light.ordinal=0; light.type=LightType::BACKLIGHT;
    result->push_back(light); return ndk::ScopedAStatus::ok();
  }
  ndk::ScopedAStatus setLightState(int32_t id,const HwLightState& state) override {
    if(id!=0) return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
    if(state.brightnessMode==BrightnessMode::LOW_PERSISTENCE)
      return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
    unsigned maximum=0;
    FILE* f=fopen(kMaximum,"re");
    if(!f) return ndk::ScopedAStatus::fromServiceSpecificError(errno);
    int parsed=fscanf(f,"%u",&maximum); fclose(f);
    if(parsed!=1 || maximum==0 || maximum>65535)
      return ndk::ScopedAStatus::fromServiceSpecificError(EIO);
    unsigned color=static_cast<unsigned>(state.color);
    unsigned level=(77*((color>>16)&255)+150*((color>>8)&255)+29*(color&255))>>8;
    unsigned panel=level*maximum/255;
    char text[24]; int length=snprintf(text,sizeof(text),"%u\n",panel);
    int fd=open(kBrightness,O_WRONLY|O_CLOEXEC);
    if(fd<0) return ndk::ScopedAStatus::fromServiceSpecificError(errno);
    ssize_t written; do { written=write(fd,text,length); } while(written<0 && errno==EINTR);
    int error=written==length?0:(errno?errno:EIO); close(fd);
    if(error) return ndk::ScopedAStatus::fromServiceSpecificError(error);
    __android_log_print(ANDROID_LOG_INFO,"A30Backlight","framework=%u panel=%u max=%u",level,panel,maximum);
    return ndk::ScopedAStatus::ok();
  }
};
int main(int argc,char** argv) {
  const char* name="android.hardware.light.ILights/default";
  if(argc>1 && strcmp(argv[1],"--declared")==0) {
    printf("declared=%d\n",AServiceManager_isDeclared(name)); return 0;
  }
  ABinderProcess_setThreadPoolMaxThreadCount(1);
  auto service=ndk::SharedRefBase::make<A30Lights>();
  binder_status_t result=AServiceManager_addService(service->asBinder().get(),name);
  __android_log_print(ANDROID_LOG_INFO,"A30Backlight","addService status=%d",result);
  if(result!=STATUS_OK) return 1;
  ABinderProcess_joinThreadPool(); return 2;
}
