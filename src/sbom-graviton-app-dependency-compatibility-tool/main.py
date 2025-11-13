import sys
import pandas as pd
import java_dependency
import python_dependency
import npm_dependency
import dotnet_dependency
import java_arm_compatibility

dependency_type = sys.argv[1]
data_file = sys.argv[2]

def main():
    result = {'status': 'success'}
    if dependency_type.lower() == 'maven':
        # Use the new java_arm_compatibility analyzer instead of java_dependency
        print("Using Java ARM compatibility analyzer for Maven dependencies")
        df = java_arm_compatibility.analyze_sbom_for_arm_compatibility(f'{data_file}')
        result = {'status': 'success', 'analyzed': len(df) if not df.empty else 0}
    elif dependency_type.lower() == 'pip':
        output_df = python_dependency.dependency_validate(f'{data_file}', f'{dependency_type}')
        print("Output Dataframe: \n")
        print(output_df)
        print("\n Writing output to excel")
        output_df.to_excel('discovery_dependencies_small.xlsx', sheet_name=f'{dependency_type}')
    elif dependency_type.lower() == 'npm':
        output_df = npm_dependency.dependency_validate(f'{data_file}', f'{dependency_type}')
        print("Output Dataframe: \n")
        print(output_df)
        print("\n Writing output to excel")
        output_df.to_excel('graviton_compatibility_npm.xlsx', sheet_name=f'{dependency_type}')
    elif dependency_type.lower() == 'nuget' or dependency_type.lower() == 'dotnet':
        output_df = dotnet_dependency.dependency_validate(f'{data_file}', f'{dependency_type}')
        print("Output Dataframe: \n")
        print(output_df)
        print("\n Writing output to excel")
        output_df.to_excel('graviton_compatibility_dotnet.xlsx', sheet_name=f'{dependency_type}')
    elif dependency_type.lower() == 'all':
        # Create a Pandas Excel writer using XlsxWriter as the engine.
        graviton_compatibility_all = pd.ExcelWriter('graviton_compatibility_all.xlsx', engine='xlsxwriter')
        # Checking the graviton compatibility for Python packages
        output_df_python = python_dependency.dependency_validate(f'{data_file}', 'pip')
        # Checking the graviton compatibility for Npm 
        output_df_npm = npm_dependency.dependency_validate(f'{data_file}', 'Npm')
        # Checking the graviton compatibility for .NET packages
        output_df_dotnet = dotnet_dependency.dependency_validate(f'{data_file}', 'nuget')
        # Write each dataframe outputs to a different worksheets.
        output_df_python.to_excel(graviton_compatibility_all, sheet_name='Python_Dependency')
        output_df_npm.to_excel(graviton_compatibility_all, sheet_name='Npm_Dependency')
        output_df_dotnet.to_excel(graviton_compatibility_all, sheet_name='DotNet_Dependency')
        # Close the Pandas Excel writer [graviton_compatibility_all] and output the Excel file.
        graviton_compatibility_all.save()
    else:
        print("No match")    

    print(result)
    return result

if __name__ == '__main__':
    main()
