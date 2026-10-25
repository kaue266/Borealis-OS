// SPDX-License-Identifier: Apache-2.0
#include "engine.h"
#include <algorithm>
#include <cctype>
#include <sstream>

namespace borealis {
static const std::string cpuBase = "/sys/devices/system/cpu/";
static const std::string gpu = "/sys/kernel/gpu/";
static const std::string ioPath = "/sys/block/mmcblk0/queue/scheduler";
static const std::string tcpPath = "/proc/sys/net/ipv4/tcp_congestion_control";
static const std::string ksmPath = "/sys/kernel/mm/ksm/run";
static const std::string usbPath = "/sys/kernel/fast_charge/force_fast_charge";
static bool numeric(const std::string& s) {
    return !s.empty() && s.size() <= 8 && std::all_of(s.begin(), s.end(),
        [](unsigned char c) { return std::isdigit(c); });
}
std::vector<std::string> words(std::string value) {
    std::replace(value.begin(), value.end(), '[', ' ');
    std::replace(value.begin(), value.end(), ']', ' ');
    std::istringstream stream(value); std::vector<std::string> list;
    for (std::string word; stream >> word;) list.push_back(word);
    return list;
}
std::string selected(std::string value) {
    const auto a = value.find('['), b = value.find(']');
    if (a != std::string::npos && b > a) return value.substr(a + 1, b - a - 1);
    auto list = words(value); return list.empty() ? "" : list.front();
}
static bool contains(const std::string& list, const std::string& choice) {
    auto values = words(list);
    return std::find(values.begin(), values.end(), choice) != values.end();
}
// Zero is a DVFS unlock sentinel, never a selectable physical frequency.
static bool frequencies(const std::string& table, std::vector<int>& values) {
    for (const auto& word : words(table)) {
        if (!numeric(word)) return false;
        int value = std::stoi(word);
        if (value > 0) values.push_back(value);
    }
    return true;
}
bool allowed(const std::string& path) {
    if (path == ioPath || path == tcpPath || path == ksmPath || path == usbPath ||
        path == gpu + "gpu_min_clock" || path == gpu + "gpu_max_clock") return true;
    for (const auto& dir : {"cpufreq/policy0/", "cpufreq/policy6/", "cpu0/cpufreq/", "cpu6/cpufreq/"})
        for (const auto& node : {"scaling_min_freq", "scaling_max_freq", "scaling_governor"})
            if (path == cpuBase + dir + node) return true;
    return false;
}
std::vector<std::string> Engine::cpus() {
    std::vector<std::string> list;
    for (int core : {0, 6}) {
        auto dir = cpuBase + "cpufreq/policy" + std::to_string(core) + "/";
        if (io_.read(dir + "scaling_available_frequencies").empty())
            dir = cpuBase + "cpu" + std::to_string(core) + "/cpufreq/";
        if (!io_.read(dir + "scaling_available_frequencies").empty()) list.push_back(dir);
    }
    return list;
}
std::vector<Change> Engine::snapshot() {
    std::vector<Change> result;
    // Restore minimum before maximum on the way down; commit also normalizes
    // the minimum to the smaller endpoint before restoring either bound.
    for (const auto& dir : cpus())
        for (const auto& node : {"scaling_min_freq", "scaling_max_freq", "scaling_governor"}) {
            auto value = selected(io_.read(dir + node));
            if (!value.empty()) result.push_back({dir + node, value});
        }
    std::vector<int> gpuValues;
    if (frequencies(io_.read(gpu + "gpu_freq_table"), gpuValues) && !gpuValues.empty())
        for (const auto& path : {gpu + "gpu_min_clock", gpu + "gpu_max_clock"}) {
            auto value = selected(io_.read(path));
            if (!value.empty()) result.push_back({path, value});
        }
    for (const auto& path : {ioPath, tcpPath, ksmPath, usbPath}) {
        auto value = selected(io_.read(path));
        if (!value.empty()) result.push_back({path, value});
    }
    return result;
}
bool Engine::cap(std::vector<Change>& plan, const std::string& dir,
        const std::string& table, const std::string& min, const std::string& max,
        const std::string& choice, int ceiling) {
    std::vector<int> numbers;
    if (!frequencies(io_.read(dir + table), numbers)) return false;
    if (numbers.empty()) return dir == gpu && (choice.empty() || choice == "auto");
    int target = 0;
    if (choice.empty() || choice == "auto") {
        for (int value : numbers) if (value <= ceiling) target = std::max(target, value);
        if (!target) target = *std::min_element(numbers.begin(), numbers.end());
    } else {
        if (!numeric(choice) || std::stoi(choice) == 0 ||
            std::find(numbers.begin(), numbers.end(), std::stoi(choice)) == numbers.end()) return false;
        target = std::stoi(choice);
    }
    auto minimum = selected(io_.read(dir + min));
    if (!numeric(minimum)) return false;
    if (std::stoi(minimum) > target) plan.push_back({dir + min, std::to_string(target)});
    plan.push_back({dir + max, std::to_string(target)});
    return true;
}
Result Engine::commit(const std::vector<Change>& plan) {
    std::vector<Change> previous;
    for (const auto& change : plan) {
        if (!allowed(change.path)) return {false, "invalid_path", change.path};
        auto value = selected(io_.read(change.path));
        if (value.empty()) return {false, "unavailable_node", change.path};
    }
    for (const auto& change : plan) {
        auto value = selected(io_.read(change.path));
        if (value == change.value) continue;
        // Record the value immediately before this write: a restored minimum
        // can appear twice while bounds are normalized in the same transaction.
        previous.push_back({change.path, value});
        if (!io_.write(change.path, change.value)) {
            bool restored = true;
            // Include the failed node: some sysfs drivers change state before
            // reporting a failure. Reverse ordering restores max before min.
            for (size_t j = previous.size(); j > 0; --j)
                restored = io_.write(previous[j - 1].path, previous[j - 1].value) && restored;
            return {false, restored ? "write_failed_rolled_back" : "rollback_failed_reboot", change.path};
        }
    }
    return {true, "applied"};
}
Result Engine::apply(const Config& c, const std::vector<Change>& defaults) {
    auto get = [&](const std::string& key) { auto it = c.find(key); return it == c.end() ? "" : it->second; };
    const auto profile = get("profile");
    auto baseline = [&](const std::string& path) {
        for (const auto& item : defaults) if (item.path == path) return item.value;
        return std::string();
    };
    if (profile != "stock" && profile != "battery" && profile != "balanced" &&
        profile != "gaming" && profile != "ultra") return {false, "invalid_profile"};
    std::vector<Change> plan;
    std::vector<int> gpuValues;
    const bool gpuTableValid = frequencies(io_.read(gpu + "gpu_freq_table"), gpuValues);
    const bool gpuUnavailable = gpuTableValid && gpuValues.empty();
    if (profile == "stock") {
        if (defaults.empty()) return {false, "no_boot_defaults"};
        for (const auto& dir : cpus())
            for (const auto& node : {"scaling_min_freq", "scaling_max_freq", "scaling_governor"})
                if (baseline(dir + node).empty()) return {false, "incomplete_boot_defaults", dir + node};
        for (const auto& change : defaults) {
            if (!allowed(change.path)) return {false, "invalid_defaults"};
            if (change.path.rfind(gpu, 0) == 0 && gpuUnavailable) continue;
            if (change.path.find("max_freq") != std::string::npos || change.path == gpu + "gpu_max_clock") {
                const auto pos = change.path.rfind('/'); const auto dir = change.path.substr(0, pos + 1);
                const bool isGpu = dir == gpu;
                if (isGpu && change.value == "0" && gpuTableValid && !gpuValues.empty()) {
                    plan.push_back(change); // Restore the driver's unlocked maximum.
                    continue;
                }
                if (!cap(plan, dir, isGpu ? "gpu_freq_table" : "scaling_available_frequencies",
                    isGpu ? "gpu_min_clock" : "scaling_min_freq", isGpu ? "gpu_max_clock" : "scaling_max_freq",
                    change.value, 0)) return {false, "invalid_defaults"};
            } else if (change.path.find("scaling_governor") != std::string::npos) {
                const auto pos = change.path.rfind('/'); const auto dir = change.path.substr(0, pos + 1);
                if (!contains(io_.read(dir + "scaling_available_governors"), change.value)) return {false, "invalid_defaults"};
                if ((change.path == ksmPath || change.path == usbPath) && change.value != "0" && change.value != "1")
                    return {false, "invalid_defaults"};
                plan.push_back(change);
            }
        }
        // Preparatory lowered minima precede maxima, then saved minima are
        // restored. This works for both increasing and decreasing limits.
        for (const auto& change : defaults) {
            if (change.path.find("min_freq") == std::string::npos && change.path != gpu + "gpu_min_clock") continue;
            const auto pos = change.path.rfind('/'); const auto dir = change.path.substr(0, pos + 1);
            if (dir == gpu && gpuUnavailable) continue;
            if (dir == gpu && change.value == "0" && gpuTableValid && !gpuValues.empty()) {
                plan.push_back(change); // Zero restores an unlocked minimum too.
                continue;
            }
            if (!contains(io_.read(dir + (dir == gpu ? "gpu_freq_table" : "scaling_available_frequencies")), change.value))
                return {false, "invalid_defaults"};
            plan.push_back(change);
        }
    } else {
        int little = 1586000, big = 1768000, gpuCap = 845000;
        if (profile == "battery") { little = 1200000; big = 1400000; gpuCap = 676000; }
        if (profile == "gaming") { little = 1794000; big = 2184000; gpuCap = 1100000; }
        if (profile == "ultra") { little = 1794000; big = 2288000; gpuCap = 1300000; }
        const auto cpuDirs = cpus();
        if (cpuDirs.empty()) return {false, "no_supported_cpu"};
        for (const auto& dir : cpuDirs) {
            bool isBig = dir.find("policy6") != std::string::npos || dir.find("cpu6") != std::string::npos;
            if (!cap(plan, dir, "scaling_available_frequencies", "scaling_min_freq", "scaling_max_freq",
                    get(isBig ? "cpu_big" : "cpu_little"), isBig ? big : little)) return {false, "invalid_cpu_frequency"};
            auto gov = get("governor");
            if (gov.empty() || gov == "default") gov = baseline(dir + "scaling_governor");
            if (!gov.empty()) {
                if (!contains(io_.read(dir + "scaling_available_governors"), gov)) return {false, "invalid_governor"};
                plan.push_back({dir + "scaling_governor", gov});
            }
        }
        if (!gpuValues.empty() && gpuValues.front() < 10000) gpuCap /= 1000;
        if (!cap(plan, gpu, "gpu_freq_table", "gpu_min_clock", "gpu_max_clock", get("gpu"), gpuCap))
            return {false, "invalid_gpu_frequency"};
    }
        // Non-clock controls are independent of the selected CPU/GPU profile.
        for (const auto& spec : std::vector<std::vector<std::string>>{
                {"io", ioPath, ioPath}, {"tcp", tcpPath, "/proc/sys/net/ipv4/tcp_available_congestion_control"}}) {
            auto choice = get(spec[0]);
            if (choice.empty() || choice == "default") choice = baseline(spec[1]);
            if (!choice.empty()) {
                if (!contains(io_.read(spec[2]), choice)) return {false, "invalid_" + spec[0]};
                plan.push_back({spec[1], choice});
            }
        }
        for (const auto& spec : std::vector<std::vector<std::string>>{{"ksm", ksmPath}, {"usb", usbPath}}) {
            auto choice = get(spec[0]);
            if (choice.empty() || choice == "default") choice = baseline(spec[1]);
            if (!choice.empty()) {
                if (choice != "0" && choice != "1") return {false, "invalid_" + spec[0]};
                if (io_.read(spec[1]).empty()) return {false, "unavailable_" + spec[0]};
                plan.push_back({spec[1], choice});
            }
        }
    if (plan.empty()) return {false, "no_supported_nodes"};
    auto result = commit(plan);
    if (result.ok && gpuUnavailable) result.detail = "applied_gpu_unavailable";
    return result;
}
} // namespace borealis
