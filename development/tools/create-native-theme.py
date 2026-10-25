#!/usr/bin/env python3
"""Create checked native overlays against the actual Android 17 resources."""
from pathlib import Path
import copy
import json
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parent.parent
source=Path('/home/android/borealisos-android17')
inventory=json.loads((root/'validation/theme-resource-inventory.json').read_text())
overlay=root/'project/vendor/borealis/overlay/base'
light={'background':'#F7F5FC','surface':'#FFFFFF','text':'#171728','muted':'#555C70',
       'accent':'#65469B','aurora':'#176556','outline':'#DEDCE9','on_accent':'#FFFFFF'}
dark={'background':'#090D15','surface':'#171D2B','text':'#F2F3FF','muted':'#AFB9CD',
      'accent':'#C5B4FF','aurora':'#8BE8D0','outline':'#313B50','on_accent':'#261C3F'}
core='frameworks/base/core/res/res'
systemui='frameworks/base/packages/SystemUI/res'
appmaps={
 'packages/apps/Contacts/res':{
    'quantum_black_text':'text','quantum_black_secondary_text':'muted','quantum_black_hint_text':'muted',
    'quickcontact_entry_sub_header_text_color':'muted','quickcontact_entry_header_text_color':'text',
    'action_bar_background':'surface','actionbar_background_color':'surface','action_bar_button_text_color':'text',
    'primary_color':'accent','primary_color_dark':'background','contacts_accent_color':'on_accent',
    'floating_action_button_icon_color':'on_accent','divider_line_color_light':'outline',
    'expanding_entry_card_background_color':'surface','expanding_entry_card_button_text_color':'text',
    'card_margin_color':'background','contextual_selection_bar_color':'surface',
    'contextual_selection_bar_status_bar_color':'background'},
 'packages/apps/Dialer/java/com/android/dialer/theme/hidden/res':{
    'dialer_theme_color':'accent','dialer_theme_color_dark':'accent','dialer_secondary_color':'aurora',
    'dialer_background_color':'background','dialer_dark_theme_color':'accent',
    'dialer_dark_theme_color_dark':'accent','dialer_dark_secondary_color':'aurora'},
 'packages/apps/Dialer/java/com/android/dialer/theme/base/res':{},
 'packages/apps/Dialer/java/com/android/dialer/theme/common/res':{
    'dialer_call_green':'aurora','dialer_divider_line_color':'outline',
    'dialer_link_color':'accent','dialer_snackbar_action_text_color':'accent'},
 'packages/apps/Messaging/res':{
    'message_text_color_incoming':'on_accent','message_text_color_outgoing':'text',
    'message_title_text':'text',
    'timestamp_text_outgoing':'muted','conversation_list_item_read':'muted',
    'conversation_list_item_unread':'text','conversation_list_name':'text',
    'conversation_list_details':'muted','conversation_background':'background',
    'action_bar_background_color':'accent','action_bar_background_color_dark':'accent',
    'action_bar_title_text_color':'on_accent','contextual_action_bar_background_color':'surface',
    'compose_send_text_color':'text','primary_color':'accent',
    'message_bubble_color_outgoing':'surface','message_body_size_text_color':'muted',
    'message_info_text':'on_accent','timestamp_text_incoming':'on_accent',
    'contact_list_text_primary':'text','contact_list_text_secondary':'muted',
    'contact_picker_background':'background','participant_list_text_primary':'text',
    'participant_list_text_secondary':'muted','people_and_options_header_text':'muted',
    'people_and_options_list_divider':'outline','settings_list_text_primary':'text',
    'settings_list_text_secondary':'muted','settings_item_title_text_primary':'text',
    'group_mms_setting_text_color':'text','sim_selector_text_primary':'text',
    'sim_selector_text_secondary':'muted','fab_color':'accent','fab_pressed_color':'aurora',
    'list_empty_text':'muted','message_text':'text','compose_message_send_color':'accent'},
 'packages/apps/DeskClock/res':{'default_background':'background'},
 'packages/apps/DocumentsUI/res':{
    'app_background_color':'background','background_floating':'surface','primary':'accent',
    'search_bar_background_light':'surface','search_bar_background_dark':'surface',
    'empty_state_text_color':'muted','color_surface_header':'surface',
    'tab_selected_text_color':'accent','tab_unselected_text_color':'muted'},
 'packages/apps/Camera2/res':{
    'mode_selector_text_color':'text','mode_selector_background_light':'surface',
    'mode_selector_background_dark':'surface','mode_selector_text_highlight_color':'aurora',
    'mode_list_background':'surface','mode_options_background':'surface','camera_gray_background':'background',
    'dialog_text_color':'text','blue_button_text_color':'accent'},
 'packages/apps/Gallery2/res':{
    'default_background':'background','albumset_background':'background',
    'albumset_label_background':'surface','album_background':'background',
    'background_screen':'background','background_toolbar':'surface',
    'background_main_toolbar':'surface','text_toolbar':'text'},
 'packages/inputmethods/LatinIME/java/res':{
    'key_text_color_lxx_light':'text','key_text_color_lxx_dark':'text',
    'key_functional_text_color_lxx_light':'accent','key_functional_text_color_lxx_dark':'accent',
    'key_text_inactive_color_lxx_light':'muted','key_text_inactive_color_lxx_dark':'muted',
    'language_on_spacebar_text_color_lxx_light':'muted','language_on_spacebar_text_color_lxx_dark':'muted',
    'key_background_lxx_light':'surface','key_background_lxx_dark':'surface',
    'key_background_pressed_lxx_light':'accent','key_background_pressed_lxx_dark':'accent',
    'suggested_word_background_selected_lxx_light':'surface','suggested_word_background_selected_lxx_dark':'surface'},
 'packages/apps/Launcher3/res':{
    'popup_color_primary_light':'surface','popup_color_primary_dark':'surface',
    'popup_text_color_light':'text','popup_text_color_dark':'text',
    'folder_background_light':'surface','folder_background_dark':'surface',
    'folder_text_color_light':'text','folder_text_color_dark':'text',
    'folder_hint_text_color_light':'muted','folder_hint_text_color_dark':'muted',
    'workspace_accent_color_light':'accent','workspace_accent_color_dark':'accent'},
 'packages/apps/Settings/res':{
    'icon_accent':'accent','homepage_network_background':'surface',
    'homepage_connected_device_background':'surface','homepage_apps_background':'surface',
    'homepage_notification_background':'surface','homepage_sound_background':'surface',
    'homepage_display_background':'surface','homepage_wallpaper_background':'surface',
    'homepage_storage_background':'surface','homepage_battery_background':'surface',
    'homepage_system_background':'surface','homepage_about_background':'surface',
    'homepage_security_background':'surface'},
 systemui:{'notification_legacy_background_color':'surface','shade_panel_fallback':'surface',
           'notification_scrim_fallback':'background','shade_header_text_color':'text',
           'shade_header_text_color_bg':'surface'},
}
changes=[];not_found=[]
def write_xml(path, tree):
    path.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(tree)
    ET.ElementTree(tree).write(path,encoding='utf-8',xml_declaration=True)
for path,mapping in appmaps.items():
    resources=inventory.get(path,{})
    if not resources:
        not_found.append({'module':path,'reason':'checkout/resource inventory incomplete'})
        continue
    for qualifier,palette in [('values',light),('values-night',dark)]:
        tree=ET.Element('resources')
        for role,value in palette.items():
            ET.SubElement(tree,'color',name='borealis_'+role).text=value
        for role,value in dark.items():
            ET.SubElement(tree,'color',name='borealis_dark_'+role).text=value
        for name,role in mapping.items():
            if resources.get(name,{}).get('type')!='color':
                if qualifier=='values':not_found.append({'module':path,'resource':name})
                continue
            # Resource names already ending in light/dark preserve their meaning.
            colors=dark if name.startswith('dialer_dark_') or name.endswith('_dark') else light if name.endswith('_light') else palette
            ET.SubElement(tree,'color',name=name).text=colors[role]
            if qualifier=='values':changes.append({'module':path,'type':'color','name':name})
        write_xml(overlay/path/qualifier/'borealis_native_colors.xml',tree)
    if path in (systemui,'packages/apps/Settings/res','packages/apps/Launcher3/res'):
        continue  # Keep modern native components' expressive theme structure.
    # Copy whole existing theme definitions so functional items remain intact.
    styles=[]
    for file in sorted((source/path/'values').glob('*.xml')):
        for item in ET.parse(file).getroot().findall('style'):
            name=item.get('name','')
            if name.startswith(('Theme.','ThemeOverlay.','Dialer.ThemeBase')) or name in ('Dialer','Dialer.Dark','AlertDialogTheme'):
                styles.append(copy.deepcopy(item))
    for qualifier,palette in [('values',light),('values-night',dark)]:
        tree=ET.Element('resources')
        for original in styles:
            style=copy.deepcopy(original)
            explicit_dark=style.get('name')=='Dialer.Dark' or '.Dark' in style.get('name','')
            existing={i.get('name'):i for i in style.findall('item')}
            updates={'android:windowBackground':'@color/borealis_background',
                     'android:colorBackground':'@color/borealis_background',
                     'android:colorAccent':'@color/borealis_accent',
                     'android:textColorPrimary':'@color/borealis_text',
                     'android:textColorSecondary':'@color/borealis_muted',
                     'android:colorControlActivated':'@color/borealis_accent',
                     'android:colorControlNormal':'@color/borealis_muted',
                     'android:dialogCornerRadius':'28dp',
                     'android:navigationBarColor':'@color/borealis_background',
                     'android:statusBarColor':'@color/borealis_background',
                     'android:windowLightStatusBar':'true' if qualifier=='values' else 'false',
                     'android:windowLightNavigationBar':'true' if qualifier=='values' else 'false'}
            # Overlays and camera viewfinder themes must not alter window structure.
            # Keep transparency/fullscreen flags and the app's original bar behavior.
            if style.get('name','').startswith('ThemeOverlay.') or path == 'packages/apps/Camera2/res':
                updates={key:value for key,value in updates.items()
                         if key not in ('android:windowBackground','android:colorBackground',
                            'android:navigationBarColor','android:statusBarColor',
                            'android:windowLightStatusBar','android:windowLightNavigationBar')}
            for attr,role in [('colorAccent','accent'),('colorPrimary','accent'),
                              ('colorPrimaryDark','background'),('colorBackgroundFloating','surface')]:
                if attr in existing:updates[attr]='@color/borealis_'+role
            for name,value in updates.items():
                if explicit_dark:
                    value=value.replace('@color/borealis_','@color/borealis_dark_')
                    if name in ('android:windowLightStatusBar','android:windowLightNavigationBar'):value='false'
                item=existing.get(name)
                if item is None:item=ET.SubElement(style,'item',name=name)
                item.text=value
            tree.append(style)
        if styles:write_xml(overlay/path/qualifier/'borealis_native_themes.xml',tree)
        if qualifier=='values':changes.extend({'module':path,'type':'style','name':s.get('name')} for s in styles)

# Phone text selectors retain disabled states while matching each explicit theme.
phone='packages/apps/Dialer/java/com/android/dialer/theme/hidden/res'
for filename,role in [('dialer_primary_text_color.xml','text'),('dialer_secondary_text_color.xml','muted'),
                      ('dialer_dark_primary_text_color.xml','text'),('dialer_dark_secondary_text_color.xml','muted')]:
    original=source/phone/'color'/filename
    if not original.is_file():continue
    for qualifier,palette in [('color',light),('color-night',dark)]:
        tree=ET.parse(original).getroot()
        colors=dark if filename.startswith('dialer_dark_') else palette
        for item in tree.findall('item'):
            item.set('{http://schemas.android.com/apk/res/android}color',colors[role])
            if item.get('{http://schemas.android.com/apk/res/android}state_enabled')=='false':
                item.set('{http://schemas.android.com/apk/res/android}alpha','0.38')
        write_xml(overlay/phone/qualifier/filename,tree)

dimens={'qs_corner_radius':'28dp','notification_corner_radius':'24dp',
        'volume_dialog_background_corner_radius':'28dp','control_corner_radius':'20dp',
        'media_output_dialog_corner_radius':'28dp','internet_dialog_corner_radius':'28dp',
        'volume_dialog_tap_target_size':'48dp','volume_ringer_drawer_item_size':'48dp',
        'volume_ringer_drawer_item_size_half':'24dp'}
tree=ET.Element('resources')
for name,value in dimens.items():
    assert inventory[systemui].get(name,{}).get('type')=='dimen', f'Unknown Android 17 SystemUI dimension {name}'
    ET.SubElement(tree,'dimen',name=name).text=value
write_xml(overlay/systemui/'values/borealis_dimens.xml',tree)
(root/'validation/native-theme.json').write_text(json.dumps({
    'source_release':'android17-release','changes':changes,'unmatched_candidates':not_found,
    'phase':'resource and native-theme integration; component layouts and firmware runtime still pending'},indent=2)+'\n')
(root/'design/tokens.json').write_text(json.dumps({'light':light,'dark':dark,
    'surface_radius_dp':24,'sheet_radius_dp':28,'touch_min_dp':48,
    'display_font':'borealis-orbit','body_font':'sans-serif','spring_damping':1,'spring_response_seconds':.35},indent=2)+'\n')
print(f'Created native overlays: {len(changes)} verified resources/themes across {len(appmaps)} modules.')
print(f'{len(not_found)} candidates were not present and were not installed as invented overlays.')
