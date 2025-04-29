import xml.etree.ElementTree as ET
import sys

# Define Android namespace globally
NS = {'android': 'http://schemas.android.com/apk/res/android'}
# Define API level for Android 12 behavior change
ANDROID_12_API_LEVEL = 31

def get_target_sdk_version(root):
    """Finds the targetSdkVersion in the manifest."""
    uses_sdk = root.find('./uses-sdk', namespaces=NS)
    if uses_sdk is not None:
        target_sdk_str = uses_sdk.get(f"{{{NS['android']}}}targetSdkVersion")
        if target_sdk_str:
            try:
                return int(target_sdk_str)
            except ValueError:
                print(f"Warning: Invalid non-integer targetSdkVersion: {target_sdk_str}. Assuming pre-Android 12 behavior.", file=sys.stderr)
                return ANDROID_12_API_LEVEL - 1 # Default to pre-12 if invalid
    print("Warning: targetSdkVersion not found in manifest. Assuming pre-Android 12 behavior.", file=sys.stderr)
    return ANDROID_12_API_LEVEL - 1 # Default to pre-12 if not found

def get_application_permission(root):
    """Finds the permission set at the application level."""
    application = root.find('./application', namespaces=NS)
    if application is not None:
        return application.get(f"{{{NS['android']}}}permission")
    return None

def is_launcher_activity(component):
    """Checks if an activity component has the MAIN/LAUNCHER intent filter."""
    intent_filters = component.findall('./intent-filter', namespaces=NS)
    for intent_filter in intent_filters:
        has_main_action = False
        has_launcher_category = False
        actions = intent_filter.findall('./action', namespaces=NS)
        for action in actions:
            if action.get(f"{{{NS['android']}}}name") == 'android.intent.action.MAIN':
                has_main_action = True
                break
        categories = intent_filter.findall('./category', namespaces=NS)
        for category in categories:
            if category.get(f"{{{NS['android']}}}name") == 'android.intent.category.LAUNCHER':
                has_launcher_category = True
                break
        if has_main_action and has_launcher_category:
            return True
    return False

def get_unprotected_exported_components(file_name):
    """
    Analyzes AndroidManifest.xml to find exported components without required permissions,
    considering targetSdkVersion.
    """
    unprotected_components = []
    try:
        tree = ET.parse(file_name)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}", file=sys.stderr)
        return []
    except FileNotFoundError:
        print(f"Error: File not found: {file_name}", file=sys.stderr)
        return []

    target_sdk = get_target_sdk_version(root)
    app_permission = get_application_permission(root)

    print(f"Info: Found targetSdkVersion: {target_sdk}", file=sys.stderr)
    if app_permission:
        print(f"Info: Found application-level permission: {app_permission}", file=sys.stderr)

    # Component types including aliases
    component_tags = ['activity', 'service', 'receiver', 'provider', 'activity-alias']

    for component_type_tag in component_tags:
        # Determine the effective component type (aliases map to activities)
        effective_component_type = 'activity' if component_type_tag == 'activity-alias' else component_type_tag

        components = root.findall(f".//application/{component_type_tag}", namespaces=NS) # Use .// to find within application

        for component in components:
            component_name = component.get(f"{{{NS['android']}}}name")
            if not component_name:
                component_name = f"Unnamed {component_type_tag}" # Handle cases where name might be missing

            exported_attr = component.get(f"{{{NS['android']}}}exported")
            intent_filters = component.findall('./intent-filter', namespaces=NS)

            # --- Determine Exported Status ---
            is_exported = False
            reason_exported = ""

            if exported_attr is not None:
                if exported_attr.lower() == 'true':
                    is_exported = True
                    reason_exported = "Explicitly exported (true)"
                else:
                    is_exported = False # Explicitly false
                    reason_exported = "Explicitly not exported (false)"
            else:
                # Handle default/implicit export based on target SDK
                if target_sdk >= ANDROID_12_API_LEVEL:
                    # Android 12+ rules: Default is false.
                    # Exception: Main launcher activities default to true (but we only care if they are IPC targets).
                    # Important: If intent filters exist, exported MUST be set, otherwise install fails.
                    # We'll treat missing 'exported' with intent filters as effectively 'false' for analysis,
                    # though it indicates an invalid manifest for API 31+.
                    if intent_filters:
                        # This state is technically invalid for API 31+ and should prevent installation.
                        is_exported = False
                        reason_exported = f"Default not exported (targetSdk >= {ANDROID_12_API_LEVEL}, intent filters present but android:exported missing - INVALID manifest)"
                    else:
                         # No intent filters, not explicitly set => default false
                         is_exported = False
                         reason_exported = f"Default not exported (targetSdk >= {ANDROID_12_API_LEVEL}, no intent filters)"

                    # Check for the specific launcher exception if it's an activity/alias
                    if effective_component_type == 'activity' and is_launcher_activity(component):
                         # Launcher activities default to true even in API 31+ if exported isn't set
                         # Note: This check might be redundant if the previous 'intent_filters' check already deemed it false/invalid
                         # because launchers *must* have the MAIN/LAUNCHER filter. Let's refine this.
                         # If filters are present and exported is MISSING on >=31, it's invalid/effectively false, EVEN if it's the launcher.
                         # The default=true for launcher only applies if filters are present AND exported is missing on SDK < 31? No, that's implicit=true.
                         # Let's stick to: on >=31, if exported is missing, it defaults to false UNLESS it's the specific launcher filter combo.
                         # Re-reading docs: The *requirement* to set exported applies if filters are present. The *default* if *no filters* are present is false.
                         # Let's simplify: If exported is not set on >=31:
                         #   - If filters are present: It's an error, treat as not exported.
                         #   - If no filters are present: It's not exported.
                         # Therefore, the only way to be exported on >=31 is explicit 'true'.
                         # Previous logic stands: treat missing exported on >=31 as false.

                         pass # Keeping the launcher check code above for reference but commenting out functional change

                else:
                    # Pre-Android 12 rules
                    if effective_component_type == 'provider':
                        is_exported = True # Providers default to true before API 31
                        reason_exported = f"Default exported (targetSdk < {ANDROID_12_API_LEVEL}, Provider)"
                    elif intent_filters:
                        is_exported = True # Activity/Service/Receiver/Alias with filters default to true
                        reason_exported = f"Implicitly exported (targetSdk < {ANDROID_12_API_LEVEL}, intent filters present)"
                    else:
                        is_exported = False # Activity/Service/Receiver/Alias without filters default to false
                        reason_exported = f"Default not exported (targetSdk < {ANDROID_12_API_LEVEL}, no intent filters)"


            # --- Determine Protection Status ---
            comp_perm = component.get(f"{{{NS['android']}}}permission")
            read_perm = component.get(f"{{{NS['android']}}}readPermission") if effective_component_type == 'provider' else None
            write_perm = component.get(f"{{{NS['android']}}}writePermission") if effective_component_type == 'provider' else None

            # Effective permission: component specific > application level
            effective_permission = comp_perm or (read_perm if effective_component_type == 'provider' else None) or \
                                   (write_perm if effective_component_type == 'provider' else None) or \
                                   app_permission

            is_protected = bool(effective_permission) # Is protected if any relevant permission is set

            # --- Flag if Exported and Unprotected ---
            if is_exported and not is_protected:
                reason_unprotected = "no component or application permission set"
                if effective_component_type == 'provider':
                     reason_unprotected = "no component permission/readPermission/writePermission or application permission set"

                unprotected_components.append((
                    effective_component_type,
                    component_name,
                    f"{reason_exported}; {reason_unprotected}"
                ))

    return unprotected_components

def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path/to/AndroidManifest.xml>")
        sys.exit(1)

    file_name = sys.argv[1]
    unprotected_components = get_unprotected_exported_components(file_name)

    component_colors = {
        'activity': '\033[92m',  # Green
        'service': '\033[94m',   # Blue
        'receiver': '\033[93m',  # Yellow
        'provider': '\033[95m',  # Purple
    }
    end_color = '\033[0m'

    print("\n--- Analysis Results ---")
    if not unprotected_components:
        print("No unprotected exported components found.")
    else:
        print("Found Unprotected Exported Components:")
        for comp_type, comp_name, reason in unprotected_components:
            color = component_colors.get(comp_type, '')
            # Ensure component name is treated as string for printing
            comp_name_str = str(comp_name) if comp_name is not None else "[Unknown Name]"
            print(f"{color}[{comp_type.capitalize()}]{end_color} {comp_name_str}\n  Reason: {reason}")

if __name__ == '__main__':
    main()
