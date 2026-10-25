#!/system/bin/sh
# Explicit legacy diagnostic mode: DNS stall detection remains enabled.
# TCP socket polling currently crashes NetworkStack on absent BPF maps.
# This does not provide BPF support, alter firewall policy, or fake validation.
umask 077
base=/data/debug/borealis-connectivity
mkdir -p "$base"
id=$(cat /proc/sys/kernel/random/boot_id)
dir="$base/$id"
mkdir -p "$dir"
exec > "$dir/actions.txt" 2>&1
date
cat /proc/uptime
if [ ! -f "$base/data-stall-original.txt" ]; then
    /system/bin/device_config get connectivity data_stall_evaluation_type > "$base/data-stall-original.txt"
fi
# Pin only this optional TCP-stall flag; keep global configuration sync enabled.
/system/bin/device_config override connectivity data_stall_evaluation_type 1
echo "device_config_override_exit=$?"
/system/bin/device_config get connectivity data_stall_evaluation_type
logcat -b all -v threadtime -f "$dir/logcat.txt" -r 1024 -n 3 &
logger=$!
trap 'kill "$logger" 2>/dev/null' EXIT HUP INT TERM
i=0
while [ "$i" -lt 18 ]; do
    date >> "$dir/processes.txt"
    cat /proc/uptime >> "$dir/processes.txt"
    for p in sys.boot_completed init.svc.adbd init.svc.netd init.svc.zygote init.svc.zygote_secondary init.svc.bootanim; do
        printf '%s=' "$p" >> "$dir/processes.txt"
        getprop "$p" >> "$dir/processes.txt"
    done
    for n in system_server surfaceflinger adbd netd com.android.networkstack.process com.android.bluetooth; do
        printf '%s=' "$n" >> "$dir/processes.txt"
        pidof "$n" >> "$dir/processes.txt"
    done
    if [ "$i" -eq 0 ] || [ "$i" -eq 6 ] || [ "$i" -eq 17 ]; then
        {
            date
            cat /proc/mounts | grep /mnt/vendor/efs
            cmd wifi status
            ip addr show wlan0
            ip route
            timeout 10 dumpsys connectivity
            timeout 10 dumpsys bluetooth_manager
            timeout 10 dumpsys activity lastanr
            dmesg | tail -n 1800
        } > "$dir/state-$i.txt" 2>&1
    fi
    i=$((i+1))
    sleep 10
done
