import os
import json

profiles_dir = r"c:\Users\ae275\OneDrive - Brunel University London\Documents\HILIGHT_DigitalTwin\DigitalTwin_Matlab\python\profiles\instruments"
precision_photons = 200
precision_mc_repeats = 100

def update_profiles():
    files = [f for f in os.listdir(profiles_dir) if f.endswith(".json")]
    for filename in files:
        filepath = os.path.join(profiles_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Update the config section
            if "config" in data:
                print(f"Updating {filename}...")
                data["config"]["precision_photons"] = precision_photons
                data["config"]["precision_mc_repeats"] = precision_mc_repeats
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            else:
                print(f"Skipping {filename}: no 'config' section found.")
        except Exception as e:
            print(f"Error updating {filename}: {e}")

if __name__ == "__main__":
    update_profiles()
