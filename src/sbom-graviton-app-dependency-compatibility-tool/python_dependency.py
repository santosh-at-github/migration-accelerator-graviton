import pandas as pd
import sys
import subprocess
import os
import re
import datetime
import json

def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def dependency_validate(data_file, type):
    data =  read_json_file(data_file)
    components = data['components']
    lines=0
    #Create a new column Compatibe on arm and timestamp
    df = pd.DataFrame()
    df["filename"]=""
    df["origin"]=""
    df["component"]=""
    df["version"]=""
    df["Compatible on Graviton?"] = ""
    df["Log Snippet"] = ""
    df["Latest version Compatible on Graviton?"] = ""
    df["Latest Log Snippet"] = ""
    df["Timestamp"] = ""
    final_tested_list=[]
    package=[]
    version=[]
    package_count=0
    with open("requirements.txt", "w+", encoding='utf-8') as f:
        for component in components:
            if component['purl'].startswith('pkg:pypi/'):
                dependency_snippet = f"""{component['name']}=={component['version']}\n"""
                f.write(dependency_snippet)
                lines=lines+1
    with open("requirements.txt", 'r', encoding='utf-8') as f:
        print(f'\n Contents of the requirements.txt is: \n {f.read()} \n')
    sys.stdout.flush()

    df = pd.DataFrame(columns=['Component', 'Version', 'Compatible on Graviton?', 'Log Snippet', 'Timestamp', 'Latest version Compatible on Graviton?', 'Latest Log Snippet'])
    #for i in range(lines):
    i=0
    with open("requirements.txt",'r', encoding='utf-8') as f:
        for i,ele in enumerate(f, start=0):
            my_package=ele.split("==")[0]
            versions=ele.split("==")[1]
            df.at[i, 'Component'] = my_package
            df.at[i, 'Version'] = versions.strip()
            print("=======package to install========")
            print(my_package)
            print(versions)
            if my_package == 'pandas':
                    print("=====package already installed======",my_package)
                    print("\n Installation Succeeded. \n")
                    df.at[i, 'Compatible on Graviton?'] = 'Yes'
                    df.at[i, 'Log Snippet'] = 'Already installed pandas version 1.5.1'
                    df.at[i, 'Timestamp'] = datetime.datetime.now()
                    df.at[i, 'Latest version Compatible on Graviton?'] = 'NA'
                    df.at[i, 'Latest Log Snippet'] = 'NA'
            else:
                try:
                    command_output=subprocess.check_output(['pip3', 'install', '-r', 'requirements.txt', '--upgrade'], stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as e:
                    print("Errors during installation")
                    #print('error>', e.output, '<')
                    command_output=e.output
                packages_output=subprocess.check_output(['pip3', 'freeze', '--all'], stderr=subprocess.STDOUT)
                packages_output_str= str(packages_output)
                    #print(f"pip freeze output:\n {packages_output_str}")
                in_pip_list=re.search(f'{my_package}.*{versions}', f'{packages_output_str}', re.MULTILINE)
                success_match = re.search(f'Successfully installed.*{my_package}-{versions}', f'{command_output}')
                success_match_2 = re.search(f'Requirement already satisfied', f'{command_output}')
                print(in_pip_list)
                print(success_match)
                print(success_match_2)
# If packag is tested , append the package and version to the list 
                if success_match or in_pip_list or success_match_2:
                    print("\n Installation Succeeded. \n")
                    df.at[i, 'Compatible on Graviton?'] = 'Yes'
                    df.at[i, 'Log Snippet'] = command_output
                    df.at[i, 'Timestamp'] = datetime.datetime.now()
                    df.at[i, 'Latest version Compatible on Graviton?'] = 'NA'
                    df.at[i, 'Latest Log Snippet'] = 'NA'
        #Uninstalling packages before moving onto the next one.
        #pip_list_output=subprocess.check_output(['pip', 'list'])
        #print(f'Before pip uninstall: {pip_list_output}')
        #command_output=subprocess.check_output(['pip3', 'uninstall', '-r', 'requirements.txt'])
        #pip_list_output=subprocess.check_output(['pip3', 'list'])
        #print(f'Before pip uninstall: {pip_list_output}')
                else:
                    print("\n Installation Failed. Trying Installation of latest version. \n")
                    df.at[i, 'Compatible on Graviton?'] = 'No'
                    df.at[i, 'Log Snippet'] = command_output
                    df.at[i, 'Timestamp'] = datetime.datetime.now()
                    try:
                        latest_command_output=subprocess.check_output(['pip3', 'install', my_package , '--upgrade'], stderr=subprocess.STDOUT)
                    except subprocess.CalledProcessError as e:
                        print("Errors during installation")
                        #print('error>', e.output, '<')
                        latest_command_output=e.output
                    latest_packages_output=subprocess.check_output(['pip3', 'freeze', '--all'], stderr=subprocess.STDOUT)
                    latest_packages_output_str= str(latest_packages_output)
        #print(f"pip freeze output:\n {latest_packages_output_str}")
                    latest_in_pip_list=re.search(f'{my_package}', f'{latest_packages_output_str}', re.MULTILINE)
                    latest_in_pip_success_match = re.search(f'Successfully installed.*{my_package}', f'{latest_command_output}')
                    latest_in_pip_success_match_2 = re.search(f'Requirement already satisfied', f'{latest_command_output}')
                    print(latest_in_pip_list)
                    print(latest_in_pip_success_match)
                    print(latest_in_pip_success_match_2)
                    if latest_in_pip_list or latest_in_pip_success_match or latest_in_pip_success_match_2:
                        print("\n Installation of latest version succeeded. \n")
                        df.at[i, 'Latest version Compatible on Graviton?'] = 'Yes'
                        df.at[i, 'Latest Log Snippet'] = latest_command_output
                    else:
                        print("\n Installation of latest version falied. \n")
                        df.at[i, 'Latest version Compatible on Graviton?'] = 'No'
                        df.at[i, 'Latest Log Snippet'] = latest_command_output
                    i=i+1
# If packag is tested , append the package and version to the list 

        with open("requirements.txt",'r', encoding='utf-8') as f:
            for ele in f:
                if versions == 'LATEST':
                    package.append(components)
                    version.append(versions)
                else:
                    (pack,ver) = ele.split("==")
                    ver=ver.strip()
                    package.append(pack)
                    version.append(ver)
        final_tested_list=list(zip(package,version))
        #print("=======Tested packages==========")
        #print(final_tested_list)

        package_count=package_count+1
        print(f'Count: {package_count}')
    return df