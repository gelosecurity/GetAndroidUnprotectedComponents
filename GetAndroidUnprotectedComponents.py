import xml.etree.ElementTree as ET

def get_unprotected_components(file_name):
    unprotected_components = []

    tree = ET.parse(file_name)
    root = tree.getroot()
    ns = {'android': 'http://schemas.android.com/apk/res/android'}

    for component_type in ['activity', 'service', 'receiver', 'provider']:
        components = root.findall(f"./application/{component_type}", namespaces=ns)

        for component in components:
            protection = component.get(f"{{{ns['android']}}}exported")
            component_name = component.get(f"{{{ns['android']}}}name")

            if protection is None:
                unprotected_components.append((component_type, component_name, 'android:exported attribute is not specified'))
            elif protection.lower() == 'true':
                unprotected_components.append((component_type, component_name, 'android:exported attribute is set to true'))

    return unprotected_components

def main():
    file_name = 'AndroidManifest.xml'
    unprotected_components = get_unprotected_components(file_name)

    component_colors = {
        'activity': '\033[92m',  # Green
        'service': '\033[94m',   # Blue
        'receiver': '\033[93m',  # Yellow
        'provider': '\033[95m',  # Purple
    }
    end_color = '\033[0m'

    print("Unprotected Components:")
    for component_type, component_name, reason in unprotected_components:
        if component_type in ['activity', 'service', 'receiver', 'provider']:
            print(f"{component_colors[component_type]}[{component_type.capitalize()}]{end_color} {component_name} ({reason})")

if __name__ == '__main__':
    main()

