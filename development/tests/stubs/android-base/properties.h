// Host property-service substitute; compositor control code is compiled unchanged.
#pragma once
#include <map>
#include <string>
#include <charconv>
namespace android::base {
inline std::map<std::string,std::string> testProperties;
inline std::string GetProperty(const std::string& key,const std::string& fallback) {
 auto it=testProperties.find(key);return it==testProperties.end()?fallback:it->second;
}
inline bool SetProperty(const std::string& key,const std::string& value) {
 testProperties[key]=value;return true;
}
inline bool GetBoolProperty(const std::string& key,bool fallback) {
 auto value=GetProperty(key,"");if(value=="1"||value=="true")return true;
 if(value=="0"||value=="false")return false;
 return fallback;
}
template<class T> T GetIntProperty(const std::string& key,T fallback) {
 auto value=GetProperty(key,"");T result{};
 auto parsed=std::from_chars(value.data(),value.data()+value.size(),result);
 return parsed.ec==std::errc{}&&parsed.ptr==value.data()+value.size()?result:fallback;
}
}
