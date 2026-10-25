// SPDX-License-Identifier: Apache-2.0
#include "engine.h"
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/strings.h>
#include <sstream>
#include <cerrno>
#include <cstring>

namespace {
class DeviceIo : public borealis::Io {
public:
    std::string read(const std::string& path) override {
        std::string value;
        if (!android::base::ReadFileToString(path, &value)) {
            const int error = errno;
            LOG(ERROR) << "Borealis node read " << path << ": " << std::strerror(error);
        }
        return android::base::Trim(value);
    }
    bool write(const std::string& path, const std::string& value) override {
        if (!borealis::allowed(path)) return false;
        if (android::base::WriteStringToFile(value + "\n", path)) return true;
        const int error = errno;
        LOG(ERROR) << "Borealis node write " << path << ": " << std::strerror(error);
        return false;
    }
};
}
int main(int argc, char** argv) {
    (void)argc;
    android::base::InitLogging(argv, android::base::LogdLogger());
    DeviceIo io; borealis::Engine engine(io);
    const std::string file = "/data/vendor/borealis/boot-defaults";
    auto bootId = io.read("/proc/sys/kernel/random/boot_id");
    std::string saved; android::base::ReadFileToString(file, &saved);
    std::istringstream stream(saved); std::string first; std::getline(stream, first);
    std::vector<borealis::Change> defaults;
    if (!bootId.empty() && first == bootId) {
        for (std::string line; std::getline(stream, line);) {
            auto separator = line.find('|');
            if (separator != std::string::npos)
                defaults.push_back({line.substr(0, separator), line.substr(separator + 1)});
        }
    } else {
        defaults = engine.snapshot(); saved = bootId + "\n";
        for (const auto& entry : defaults) saved += entry.path + "|" + entry.value + "\n";
        if (bootId.empty() || !android::base::WriteStringToFile(saved, file, 0600, 0, 0, false)) {
            android::base::SetProperty("vendor.borealis.perf.status", "error_no_boot_snapshot");
            return 1;
        }
    }
    borealis::Config config;
    config["profile"] = android::base::GetProperty("borealis.perf.profile",
        android::base::GetProperty("persist.borealis.perf.profile", "balanced"));
    for (const auto& key : {"cpu_little", "cpu_big", "gpu", "governor"})
        config[key] = android::base::GetProperty(std::string("borealis.perf.") + key, "auto");
    // Only non-clock options persist. High clocks require a fresh selection
    // each boot and do not run before Android reports boot completion.
    for (const auto& key : {"io", "tcp", "ksm", "usb"})
        config[key] = android::base::GetProperty(std::string("persist.borealis.perf.") + key, "default");
    if (config["governor"] == "auto") config["governor"] = "default";
    const auto result = engine.apply(config, defaults);
    android::base::SetProperty("vendor.borealis.perf.error_path", result.errorPath);
    android::base::SetProperty("vendor.borealis.perf.status", (result.ok ? "ok_" : "error_") + result.detail);
    if (result.ok) android::base::SetProperty("vendor.borealis.perf.active", config["profile"]);
    LOG(INFO) << "Borealis performance: " << result.detail;
    return result.ok ? 0 : 1;
}
