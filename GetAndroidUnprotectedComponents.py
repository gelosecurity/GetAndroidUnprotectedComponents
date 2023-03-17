import xml.etree.ElementTree as ET

def get_startable_unprotected_components(file_name):
    startable_unprotected_components = []

    tree = ET.parse(file_name)
    root = tree.getroot()
    ns = {'android': 'http://schemas.android.com/apk/res/android'}

    for component_type in ['activity', 'service', 'receiver', 'provider']:
        components = root.findall(f"./application/{component_type}", namespaces=ns)

        for component in components:
            protection = component.get(f"{{{ns['android']}}}exported")
            component_name = component.get(f"{{{ns['android']}}}name")
            component_permission = component.get(f"{{{ns['android']}}}permission")
            intent_filters = component.findall(f"./intent-filter", namespaces=ns)

            if protection is not None and protection.lower() == 'true':
                reason = None
                if component_permission:
                    reason = f"android:permission attribute is specified: {component_permission}"
                elif intent_filters:
                    reason = "Intent filters are present"
                
                if reason:
                    startable_unprotected_components.append((component_type, component_name, reason))

    return startable_unprotected_components

def main():
    file_name = 'AndroidManifest.xml'
    startable_unprotected_components = get_startable_unprotected_components(file_name)

    component_colors = {
        'activity': '\033[92m',  # Green
        'service': '\033[94m',   # Blue
        'receiver': '\033[93m',  # Yellow
        'provider': '\033[95m',  # Purple
    }
    end_color = '\033[0m'

    print("Startable Unprotected Components:")
    for component_type, component_name, reason in startable_unprotected_components:
        if component_type in ['activity', 'service', 'receiver', 'provider']:
            print(f"{component_colors[component_type]}[{component_type.capitalize()}]{end_color} {component_name} ({reason})")

if __name__ == '__main__':
    main()

