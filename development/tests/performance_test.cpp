// SPDX-License-Identifier: Apache-2.0
#include "../project/vendor/borealis/performance/engine.h"
#include <cassert>
#include <iostream>
#include <map>
using namespace borealis;
const std::string little = "/sys/devices/system/cpu/cpufreq/policy0/";
const std::string big = "/sys/devices/system/cpu/cpufreq/policy6/";
const std::string gpuPath = "/sys/kernel/gpu/";
struct Fake : Io {
    std::map<std::string,std::string> values;
    std::vector<Change> writes;
    std::string fail;
    std::string failValue;
    bool failed = false;
    Fake() {
        for (auto dir : {little, big}) {
            values[dir+"scaling_available_frequencies"] = dir == big ? "2288000 2184000 1768000 1400000 1000000" : "1794000 1586000 1200000 800000";
            values[dir+"scaling_available_governors"] = "schedutil interactive performance";
            values[dir+"scaling_governor"] = "schedutil";
            values[dir+"scaling_min_freq"] = dir == big ? "1000000" : "800000";
            values[dir+"scaling_max_freq"] = dir == big ? "2288000" : "1794000";
        }
        values[gpuPath+"gpu_freq_table"] = "1300000 1100000 845000 676000 260000";
        values[gpuPath+"gpu_min_clock"] = "260000"; values[gpuPath+"gpu_max_clock"] = "1300000";
        values["/sys/block/mmcblk0/queue/scheduler"] = "noop deadline [maple]";
        values["/proc/sys/net/ipv4/tcp_available_congestion_control"] = "cubic westwood reno";
        values["/proc/sys/net/ipv4/tcp_congestion_control"] = "westwood";
        values["/sys/kernel/mm/ksm/run"] = "0";
        values["/sys/kernel/fast_charge/force_fast_charge"] = "0";
    }
    std::string read(const std::string& p) override { return values.count(p) ? values[p] : ""; }
    bool write(const std::string& p,const std::string& v) override {
        writes.push_back({p,v});
        if (p == fail && !failed && (failValue.empty() || v == failValue)) { failed = true; return false; }
        if (!allowed(p)) return false;
        if (p.find("max_freq") != std::string::npos) {
            auto dir=p.substr(0,p.rfind('/')+1);
            if (std::stoi(v)<std::stoi(values[dir+"scaling_min_freq"])) return false;
        }
        if (p.find("min_freq") != std::string::npos) {
            auto dir=p.substr(0,p.rfind('/')+1);
            if (std::stoi(v)>std::stoi(values[dir+"scaling_max_freq"])) return false;
        }
        if (p == "/sys/block/mmcblk0/queue/scheduler") {
            values[p]="";
            for (const auto& choice : {"noop", "deadline", "maple"})
                values[p] += (v == choice ? "[" + v + "]" : std::string(choice)) + " ";
        } else values[p]=v;
        return true;
    }
};
int main() {
    {
        Fake f; Engine e(f); auto r=e.apply({{"profile","balanced"}},e.snapshot()); assert(r.ok);
        assert(f.values[big+"scaling_max_freq"]=="1768000"); assert(f.values[gpuPath+"gpu_max_clock"]=="845000");
    }
    {
        Fake f; Engine e(f); auto before=f.values;
        assert(!e.apply({{"profile","ultra"},{"gpu","1300001"}},e.snapshot()).ok);
        assert(f.writes.empty()); assert(f.values==before);
        assert(!e.apply({{"profile","balanced"},{"tcp","westwood;reboot"}},e.snapshot()).ok);
        assert(f.writes.empty());
    }
    {
        Fake f; Engine e(f); auto before=f.values; f.fail=gpuPath+"gpu_max_clock";
        auto r=e.apply({{"profile","battery"}},e.snapshot()); assert(!r.ok);
        assert(r.detail=="write_failed_rolled_back"); assert(f.values==before);
    }
    {
        Fake f; Engine e(f); auto baseline=e.snapshot();
        f.values[big+"scaling_min_freq"]="2184000";
        assert(e.apply({{"profile","battery"}},baseline).ok);
        assert(f.values[big+"scaling_min_freq"]=="1400000");
        assert(e.apply({{"profile","stock"}},baseline).ok);
        assert(f.values[big+"scaling_max_freq"]=="2288000"); assert(f.values[big+"scaling_min_freq"]=="1000000");
    }
    {
        Fake f; Engine e(f); auto baseline=e.snapshot();
        baseline.push_back({"/sys/class/thermal/thermal_zone0/trip_point_0_temp","200000"});
        assert(!e.apply({{"profile","stock"}},baseline).ok); assert(f.writes.empty());
        assert(!allowed("/sys/kernel/gpu/../gpu_max_clock"));
    }
    {
        Fake f; Engine e(f);
        f.values[gpuPath+"gpu_freq_table"]="1300 1100 845 676 260";
        f.values[gpuPath+"gpu_min_clock"]="260"; f.values[gpuPath+"gpu_max_clock"]="1300";
        assert(e.apply({{"profile","balanced"}},e.snapshot()).ok); assert(f.values[gpuPath+"gpu_max_clock"]=="845");
    }
    {
        Fake f; Engine e(f); f.values.erase("/sys/kernel/fast_charge/force_fast_charge");
        assert(!e.apply({{"profile","balanced"},{"usb","1"}},e.snapshot()).ok); assert(f.writes.empty());
    }
    {
        Fake f; Engine e(f); f.values[big+"scaling_max_freq"]="1768000"; auto baseline=e.snapshot();
        assert(e.apply({{"profile","ultra"},{"cpu_big","2288000"}},baseline).ok);
        f.values[big+"scaling_min_freq"]="2184000";
        assert(e.apply({{"profile","stock"}},baseline).ok);
        assert(f.values[big+"scaling_max_freq"]=="1768000"); assert(f.values[big+"scaling_min_freq"]=="1000000");
    }
    {
        Fake f; Engine e(f); auto baseline=e.snapshot();
        assert(e.apply({{"profile","balanced"},{"governor","interactive"},{"io","deadline"},{"tcp","cubic"},{"ksm","1"}},baseline).ok);
        assert(e.apply({{"profile","balanced"},{"governor","default"},{"io","default"},{"tcp","default"},{"ksm","default"}},baseline).ok);
        assert(f.values[big+"scaling_governor"]=="schedutil"); assert(selected(f.values["/sys/block/mmcblk0/queue/scheduler"])=="maple");
        assert(f.values["/proc/sys/net/ipv4/tcp_congestion_control"]=="westwood"); assert(f.values["/sys/kernel/mm/ksm/run"]=="0");
    }
    {
        Fake f; Engine e(f); auto baseline=e.snapshot();
        assert(e.apply({{"profile","stock"},{"ksm","1"},{"usb","1"}},baseline).ok);
        assert(f.values["/sys/kernel/mm/ksm/run"]=="1"); assert(f.values["/sys/kernel/fast_charge/force_fast_charge"]=="1");
    }
    {
        Fake f; Engine e(f); f.values[big+"scaling_max_freq"]="1768000"; auto baseline=e.snapshot();
        f.values[big+"scaling_max_freq"]="2288000"; f.values[big+"scaling_min_freq"]="2184000";
        auto before=f.values; f.fail=big+"scaling_min_freq"; f.failValue="1000000";
        auto r=e.apply({{"profile","stock"}},baseline);
        assert(!r.ok && r.detail=="write_failed_rolled_back"); assert(f.values==before);
    }
    {
        Fake f; Engine e(f); f.values[gpuPath+"gpu_freq_table"]="0 ";
        auto baseline=e.snapshot();
        auto result=e.apply({{"profile","balanced"}},baseline);
        assert(result.ok && result.detail=="applied_gpu_unavailable");
        for (const auto& change : f.writes) assert(change.path.rfind(gpuPath,0)!=0);
        assert(e.apply({{"profile","stock"}},baseline).ok);
        f.writes.clear();
        assert(!e.apply({{"profile","balanced"},{"gpu","0"}},baseline).ok);
        assert(f.writes.empty());
    }
    {
        Fake f; Engine e(f); f.values.erase(gpuPath+"gpu_freq_table");
        assert(e.apply({{"profile","balanced"}},e.snapshot()).ok);
        f.writes.clear();
        assert(!e.apply({{"profile","gaming"},{"gpu","1100000"}},e.snapshot()).ok);
        assert(f.writes.empty());
    }
    {
        Fake f; Engine e(f); f.values[gpuPath+"gpu_max_clock"]="0";
        f.values[gpuPath+"gpu_min_clock"]="0"; auto baseline=e.snapshot();
        assert(e.apply({{"profile","battery"}},baseline).ok);
        assert(e.apply({{"profile","stock"}},baseline).ok);
        assert(f.values[gpuPath+"gpu_max_clock"]=="0");
        assert(f.values[gpuPath+"gpu_min_clock"]=="0");
    }
    {
        Fake f; Engine e(f); auto baseline=e.snapshot();
        f.values.erase(little+"scaling_max_freq");
        auto result=e.apply({{"profile","balanced"}},baseline);
        assert(!result.ok && result.detail=="unavailable_node");
        assert(result.errorPath==little+"scaling_max_freq"); assert(f.writes.empty());
        auto partial=e.snapshot();
        result=e.apply({{"profile","stock"}},partial);
        assert(!result.ok && result.detail=="incomplete_boot_defaults");
        assert(f.writes.empty());
    }
    {
        Fake f; Engine e(f); f.values[gpuPath+"gpu_freq_table"]="0 845000 676000 260000";
        assert(e.apply({{"profile","balanced"}},e.snapshot()).ok);
        assert(f.values[gpuPath+"gpu_max_clock"]=="845000");
        f.writes.clear();
        assert(!e.apply({{"profile","balanced"},{"gpu","0"}},e.snapshot()).ok);
        assert(f.writes.empty());
    }
    std::cout << "16 performance scenarios passed, including GPU unlock sentinels, unavailable GPU and read diagnostics\n";
}
