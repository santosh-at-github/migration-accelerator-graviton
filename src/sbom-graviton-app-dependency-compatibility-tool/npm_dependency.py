import pandas as pd
import sys
import subprocess
import os
import re
import datetime
import json
import shutil

BASH_SCRIPT_NAME = 'npm-compatibility-check.sh'

#temp name of the package.json that will be created
TEMP_NPM_PACKAGE_JSON = "package.json"

def create_temp_package_json(package_name, version, output_path=TEMP_NPM_PACKAGE_JSON):
    """
    Generates a temporary package.json file with a single dependency.
    It will NOT include a 'test' script by default, allowing npm test to
    correctly report 'missing script' if the original package doesn't have one.
    """
    package_json_content = {
        "name": "temp-compat-test",
        "version": "1.0.0",
        "description": f"Temporary package.json for {package_name}@{version}",
        "main": "index.js",
        "scripts": {}, 
        "dependencies": {
            package_name: version
        },
        "license": "ISC"
    }
    try:
        with open(output_path, 'w') as f:
            json.dump(package_json_content, f, indent=2)
    except IOError as e:
        print(f"Error writing temporary package.json to {output_path}: {e}")
        raise

def clean_npm_artifacts():
    # removes node_modules, package-lock.json, and the temporary package.json
    if os.path.exists("node_modules"):
        try:
            shutil.rmtree("node_modules")
        except OSError as e:
            print(f"Error removing node_modules: {e}")
    if os.path.exists("package-lock.json"):
        try:
            os.remove("package-lock.json")
        except OSError as e:
            print(f"Error removing package-lock.json: {e}")
    if os.path.exists(TEMP_NPM_PACKAGE_JSON):
        try:
            os.remove(TEMP_NPM_PACKAGE_JSON)
        except OSError as e:
            print(f"Error removing {TEMP_NPM_PACKAGE_JSON}: {e}")

def dependency_validate(sbom_file_path, data_file=None, type=None,
                        output_format="excel", output_filename="npm_compatibility_results"):
    
    clean_npm_artifacts()

    # read the SBOM JSON
    try:
        with open(sbom_file_path, 'r') as f:
            sbom_data = json.load(f)
        sbom_components = sbom_data.get("components", [])
        if not sbom_components:
            print("Warning: No components found in SBOM.json. Returning empty DataFrame.")
            df = pd.DataFrame(columns=['Applications', 'Origin', 'Component', 'Version',
                                        'Compatible on Graviton?', 'Timestamp', 'Error Snippet',
                                        'Native Build Detected', 'Load Test Success'])
            return df
    except FileNotFoundError:
        print(f"Error: SBOM file not found at {sbom_file_path}. Exiting script.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing SBOM JSON from {sbom_file_path}: {e}. Exiting script.")
        sys.exit(1)

    #make the dataframe
    df_data = []
    for component in sbom_components:
        if component.get("type") == "library":
            df_data.append({
                'Applications': 'SBOM-Discovered',
                'Origin': 'SBOM-Discovered',
                'Component': component.get("name"),
                'Version': component.get("version")
            })
    df_results = pd.DataFrame(df_data)

    if data_file and type:
        try:
            df_excel = pd.read_excel(data_file, usecols=[
                                            'Applications', 'Origin', 'Component', 'Version'], sheet_name=type)
            df_results.set_index(['Component', 'Version'], inplace=True)
            df_excel.set_index(['Component', 'Version'], inplace=True)
            df_results.update(df_excel)
            df_results.reset_index(inplace=True)
        except FileNotFoundError:
            print(f"Warning: Excel data file not found at {data_file}. Proceeding with data from SBOM only.")
        except KeyError as e:
            print(f"Warning: Missing expected column in Excel file or sheet '{type}': {e}. Proceeding with data from SBOM only.")
        except Exception as e:
            print(f"Warning: An unexpected error occurred while reading Excel: {e}. Proceeding with data from SBOM only.")

    if 'Applications' not in df_results.columns: df_results['Applications'] = 'SBOM-Discovered'
    if 'Origin' not in df_results.columns: df_results['Origin'] = 'SBOM-Discovered'
    df_results["Compatible on Graviton?"] = "Not Tested"
    df_results["Timestamp"] = ""
    df_results["Error Snippet"] = ""
    df_results["Native Build Detected"] = "No"
    df_results["Load Test Success"] = "No"

    bash_script_path = os.path.join(os.getcwd(), BASH_SCRIPT_NAME)

    #bash script executable 
    try:
        subprocess.run(['chmod', '+x', bash_script_path], check=True, capture_output=True, text=True)
    except Exception as e:
        print(f"Error making '{BASH_SCRIPT_NAME}' executable: {e}")
        df_results["Compatible on Graviton?"] = "Setup Error"
        df_results["Error Snippet"] = f"Failed to make bash script executable: {e}"
        df_results["Timestamp"] = datetime.datetime.now()
        return df_results

    print(f"\n--- Starting compatibility checks for {len(df_results)} packages ---")

    for index, row in df_results.iterrows():
        package_name = row['Component']
        version = row['Version']
        #console output
        print(f"\n========================================================")
        print(f"Testing {package_name}@{version} (Package {index + 1}/{len(df_results)})")
        print(f"========================================================")

        try:
            clean_npm_artifacts()
            create_temp_package_json(package_name, str(version), TEMP_NPM_PACKAGE_JSON)

            bash_command = [bash_script_path]

            bash_process = subprocess.run(
                bash_command,
                capture_output=True,
                text=True,
                check=False
            )

            try:
                bash_output_json = json.loads(bash_process.stdout.strip())
                install_status = bash_output_json.get("install_status", "Failed")
                error_snippet = bash_output_json.get("error_details", "N/A")
                native_build_detected = bash_output_json.get("native_build_detected", "No")
                load_test_success = bash_output_json.get("load_test_success", "No")

                df_results.at[index, 'Compatible on Graviton?'] = "Yes" if install_status == "Success" else "No"
                df_results.at[index, 'Error Snippet'] = error_snippet
                df_results.at[index, 'Native Build Detected'] = native_build_detected
                df_results.at[index, 'Load Test Success'] = load_test_success

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON output from bash script for {package_name}@{version}: {e}")
                print(f"Bash script STDOUT:\n{bash_process.stdout}")
                print(f"Bash script STDERR:\n{bash_process.stderr}")
                df_results.at[index, 'Compatible on Graviton?'] = "No"
                df_results.at[index, 'Error Snippet'] = f"JSON parse error: {e}. Bash output:\n{bash_process.stdout}\n{bash_process.stderr}"
            except Exception as e:
                print(f"Unexpected error processing bash output for {package_name}@{version}: {e}")
                df_results.at[index, 'Compatible on Graviton?'] = "No"
                df_results.at[index, 'Error Snippet'] = f"Unexpected error processing bash output: {e}"

            if bash_process.returncode != 0:
                print(f"Bash script returned non-zero exit code {bash_process.returncode} for {package_name}@{version}.")
                if df_results.at[index, 'Compatible on Graviton?'] == "Yes":
                     df_results.at[index, 'Compatible on Graviton?'] = "No"
                if "Error Snippet" not in df_results.at[index, 'Error Snippet']:
                    df_results.at[index, 'Error Snippet'] += f"\nBash script exited with code {bash_process.returncode}. Full stderr:\n{bash_process.stderr}"

        except FileNotFoundError:
            print(f"Error: Bash script '{BASH_SCRIPT_NAME}' not found. Skipping {package_name}@{version}.")
            df_results.at[index, 'Compatible on Graviton?'] = "Bash Script Not Found"
            df_results.at[index, 'Error Snippet'] = f"'{BASH_SCRIPT_NAME}' not found."
        except Exception as e:
            print(f"An unexpected error occurred during test for {package_name}@{version}: {e}")
            df_results.at[index, 'Compatible on Graviton?'] = "Error During Test"
            df_results.at[index, 'Error Snippet'] = f"Python script error during test: {e}"

        df_results.at[index, 'Timestamp'] = datetime.datetime.now()

    print("\n--- Final Compatibility Results ---")
    print(df_results)

    clean_npm_artifacts()

    #output file
    final_output_filepath = ""
    try:
        if not df_results.empty:
            if output_format.lower() == "excel":
                final_output_filepath = f"{output_filename}.xlsx"
                df_results.to_excel(final_output_filepath, index=False)
                print(f"\nResults successfully saved to {final_output_filepath}")
            elif output_format.lower() == "csv":
                final_output_filepath = f"{output_filename}.csv"
                df_results.to_csv(final_output_filepath, index=False)
                print(f"\nResults successfully saved to {final_output_filepath}")
            else:
                print(f"\nWarning: Unsupported output format '{output_format}'. Results not saved to file.")
        else:
            print(f"\nWarning: DataFrame is empty. No output file will be generated.")
    except Exception as e:
        print(f"\nERROR: Failed to save results to file ({output_format}). Details: {e}")
        if "No such file or directory" in str(e) and output_format.lower() == "excel":
            print("If saving to Excel (.xlsx), ensure 'openpyxl' is installed: pip install openpyxl")
        elif "No such file or directory" in str(e):
            print("Check if the output directory exists and you have write permissions.")

    return df_results