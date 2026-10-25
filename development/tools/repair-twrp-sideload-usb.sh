#!/sbin/sh
# Temporary configfs correction. No partition, recovery image or data writes.
# TWRP's init.recovery.usb.rc keeps ffs.mtp linked even when MTP is stopped for
# sideload. A gadget cannot bind while one of its FunctionFS functions is closed.
set -u
base=/sys/kernel/config/usb_gadget/g1
config=$base/configs/c.1
mtp_link=$config/ffs.mtp
adb_link=$config/ffs.adb
log=/tmp/borealis-sideload-usb.log
marker=/tmp/borealis-sideload-usb.pid
[ "$(id -u)" = 0 ] || exit 1
[ -L "$mtp_link" ] && [ -L "$adb_link" ] || exit 2
original_mtp=$(readlink "$mtp_link")
case "$original_mtp" in
  *functions/ffs.mtp) ;;
  *) exit 3 ;;
esac
controller=$(getprop sys.usb.controller)
[ "$controller" = 13600000.dwc3 ] || exit 4
# A shell launched by ADB inherits adbd's accounting group. Move ONLY this
# helper into the already existing recovery accounting group so that TWRP's
# stop-adbd operation does not kill it. No CPU quotas/controllers are changed.
recovery_pid=${1:-}
case "$recovery_pid" in
  ''|*[!0-9]*) exit 9 ;;
esac
[ "$(cat "/proc/$recovery_pid/comm")" = recovery ] || exit 10
recovery_group=/acct/uid_0/pid_$recovery_pid/cgroup.procs
[ -w "$recovery_group" ] || exit 11
if [ -f "$marker" ]; then
  previous=$(cat "$marker")
  if kill -0 "$previous" 2>/dev/null; then exit 5; fi
fi
echo $$ > "$recovery_group" || exit 12
echo $$ > "$marker"
removed=0
pending_bind=0

note() { echo "$(date +%s): $*" >> "$log"; }
unbind() { printf '\n' > "$base/UDC" 2>/dev/null || true; }
restore() {
  if [ "$removed" = 1 ]; then
    unbind
    if [ ! -e "$mtp_link" ] && [ ! -L "$mtp_link" ]; then
      ln -s "$original_mtp" "$mtp_link" || return 1
    fi
    removed=0
    pending_bind=1
    note 'restored original MTP link'
  fi
}
cleanup() {
  restore || true
  # Restore only if normal ADB+MTP is selected. The program never changes modes
  # itself and does not start a sideload operation or send an installation ZIP.
  if [ "$(getprop sys.usb.config)" = mtp,adb ]; then
    printf '%s\n' "$controller" > "$base/UDC" 2>/dev/null || true
  fi
  rm -f "$marker"
  note 'watcher stopped'
}
trap cleanup EXIT
trap 'exit 0' HUP INT TERM
note 'watcher started; waiting for a human-selected sideload mode'
iterations=0
while [ "$iterations" -lt 900 ] || [ "$removed" = 1 ]; do
  iterations=$((iterations + 1))
  mode=$(getprop sys.usb.config)
  daemon=$(getprop init.svc.adbd)
  if [ "$mode" = adb ] && [ "$daemon" = stopped ] && [ "$removed" = 0 ]; then
    # Remove precisely the inactive MTP function, never the ADB function.
    [ -L "$mtp_link" ] && [ "$(readlink "$mtp_link")" = "$original_mtp" ] || exit 6
    unbind
    rm "$mtp_link" || exit 7
    removed=1
    pending_bind=1
    note 'removed inactive MTP link for sideload'
  elif [ "$mode" = mtp,adb ] && [ "$removed" = 1 ]; then
    restore || exit 8
  fi
  if [ "$pending_bind" = 1 ] && [ -e /dev/usb-ffs/adb/ep1 ]; then
    # Wait for both FunctionFS servers when restoring the normal configuration.
    if [ "$mode" = adb ] || { [ "$mode" = mtp,adb ] && [ -e /dev/usb-ffs/mtp/ep1 ]; }; then
      if [ "$(cat "$base/UDC")" = "$controller" ] || printf '%s\n' "$controller" > "$base/UDC" 2>/dev/null; then
        pending_bind=0
        note "USB gadget bound in mode $mode"
      fi
    fi
  fi
  sleep 1
done
