# .NET Application ARM Compatibility Guide

## Introduction

The increasing prevalence of ARM architecture across diverse computing landscapes, including cloud infrastructure (like AWS Graviton), edge computing devices, and embedded systems, necessitates careful consideration of application compatibility across different processor architectures. While .NET's fundamental design promotes platform independence through its Common Language Runtime (CLR), ensuring seamless operation on ARM processors requires a focused analysis, particularly when dealing with native libraries and platform-specific code.

This guide provides a comprehensive approach for analyzing .NET application dependencies to determine their compatibility with ARM-based processors and outlines the essential information needed to achieve a high degree of confidence in this compatibility.

## Leveraging Available Artifacts for Dependency Analysis

Each build artifact associated with a .NET application offers a unique perspective on its dependencies and overall build configuration. By meticulously examining these artifacts, a detailed understanding of the application's reliance on external components can be established, forming the basis for an ARM compatibility assessment.

### Analyzing Project Files (.csproj, .vbproj, .fsproj)

For .NET projects, the project file serves as the central configuration file, declaring direct and transitive dependencies, specifying build configurations, and defining the target frameworks and runtime identifiers.

#### Extracting Direct and Transitive Dependencies

.NET's core functionality includes the automatic resolution of transitive dependencies based on the direct dependencies declared in the project file. This means that if your application directly depends on package A, and package A in turn depends on package B, NuGet will include both A and B in the project's dependencies.

To visualize these intricate relationships, .NET provides several commands:

```bash
dotnet list package --include-transitive
```

This generates a hierarchical representation of all dependencies, both direct and transitive. Understanding this full dependency graph is crucial because even if a direct dependency appears to be platform-independent, it might rely on a transitive dependency with architecture-specific requirements.

#### Understanding Runtime Identifiers (RIDs)

.NET employs Runtime Identifiers to define the target platform for which an application is built:

- **linux-arm64**: Linux ARM64 (AWS Graviton)
- **win-arm64**: Windows ARM64
- **osx-arm64**: macOS ARM64
- **linux-x64**: Linux x64
- **win-x64**: Windows x64

For ARM compatibility analysis, specifying the correct RID is crucial as it determines which native assets are included in the build.

Example of specifying ARM64 runtime in a project file:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
    <RuntimeIdentifier>linux-arm64</RuntimeIdentifier>
  </PropertyGroup>
</Project>
```

#### Package References and Native Dependencies

The project file also defines the NuGet package references used by the application. Certain packages include native libraries that are architecture-specific.

Example of a package reference that might include native dependencies:

```xml
<PackageReference Include="System.Drawing.Common" Version="6.0.0" />
<PackageReference Include="Microsoft.Data.SqlClient" Version="4.1.0" />
```

By examining the `<PackageReference>` elements, developers can identify dependencies that might require ARM-specific versions or alternatives.

#### Target Framework Considerations

The `<TargetFramework>` element specifies which version of .NET the application targets:

```xml
<TargetFramework>net6.0</TargetFramework>
```

For ARM compatibility:
- **.NET 6+**: Full ARM64 support with optimized performance
- **.NET 5**: ARM64 support available
- **.NET Core 3.1**: ARM64 support with some limitations
- **.NET Framework**: Not supported on ARM64

### Examining the Software Bill of Materials (SBOM)

A Software Bill of Materials (SBOM) offers a comprehensive and detailed inventory of all software components utilized by a .NET application, extending beyond the dependencies explicitly declared in project files to include transitive dependencies and potentially components bundled within assemblies.

Common SBOM formats include:
- **CycloneDX**: A widely adopted SBOM standard that can represent dependency relationships
- **SPDX**: Another prominent open-source standard focused on communicating software components, licenses, copyrights, and security information

Generating an SBOM can be achieved through various tools like:
- AWS Inspector SBOM Generator
- Syft
- Trivy
- CycloneDX CLI

Generating an SBOM directly from the application's published output can be particularly useful as it can reveal dependencies that might not be explicitly listed in the project file, such as those included through framework references or runtime packages.

While the primary focus of SBOM formats is on identifying software components and their metadata, some tools and extensions might include information related to the target architecture for which a component was built. Therefore, a careful examination of the metadata within the SBOM, such as component properties or descriptions, might yield clues about the intended architecture support of specific dependencies.

### Inspecting .NET Assemblies

The .NET assembly is the standard deployment unit for .NET applications and libraries, containing the compiled Intermediate Language (IL) code of the application along with any bundled resources, which can include configuration files, embedded resources, and potentially native libraries.

#### Viewing Assembly Contents

The contents of a .NET assembly can be examined using various tools:

```bash
# Using ildasm (IL Disassembler)
ildasm myapp.dll

# Using dotnet-dump
dotnet-dump collect -p <process-id>

# Using reflection-based tools
dotnet list package --include-transitive
```

This analysis can reveal the directory structure and identify any native libraries or platform-specific components.

Look for:
- `runtimes/` directories with platform-specific assets
- `lib/` directories containing native libraries
- `runtimes/linux-arm64/native/` for ARM64-specific native libraries
- `runtimes/win-arm64/native/` for Windows ARM64 native libraries

A directory structure like `runtimes/linux-arm64/native/` within a NuGet package is a strong indicator that the dependency includes native libraries specifically compiled for the Linux ARM64 architecture.

#### Analyzing Assembly Dependencies

The .NET runtime provides tools to analyze assembly dependencies:

```bash
# Check assembly dependencies
dotnet deps myapp.dll

# Analyze runtime dependencies
dotnet publish -r linux-arm64 --self-contained false
```

By examining the compiled IL code and metadata, these tools can identify the packages and assemblies that the application relies upon. This analysis can be particularly helpful in detecting dependencies on platform-specific APIs within the .NET runtime or external libraries.

#### Inspecting Manifest and Metadata

Every .NET assembly contains metadata about its contents, including information about dependencies, target framework, and potentially, details about native libraries.

```bash
# View assembly metadata
dotnet --info
ildasm /metadata myapp.dll
```

### Native Library Analysis

.NET applications can include native libraries through several mechanisms:

#### P/Invoke Declarations

Platform Invoke (P/Invoke) allows .NET code to call functions in native libraries. These declarations can indicate architecture-specific dependencies:

```csharp
[DllImport("kernel32.dll")]
public static extern IntPtr LoadLibrary(string lpFileName);

[DllImport("libssl.so.1.1", EntryPoint = "SSL_library_init")]
public static extern int SSL_library_init();
```

The presence of such declarations suggests that the application relies on native libraries that must be available for the target ARM architecture.

#### NuGet Package Native Assets

Many NuGet packages include native libraries in their `runtimes` folder structure:

```
runtimes/
├── linux-arm64/
│   └── native/
│       └── libexample.so
├── linux-x64/
│   └── native/
│       └── libexample.so
└── win-x64/
    └── native/
        └── example.dll
```

This structure indicates that the package provides architecture-specific native libraries.

## ARM Compatibility Assessment Framework

### Dependency Classification

Based on the analysis of the artifacts described above, dependencies can be classified into several categories regarding their ARM compatibility:

#### 1. Fully Compatible
- Pure managed .NET assemblies without native dependencies
- Packages that explicitly provide ARM64 native libraries
- Microsoft.* packages (generally ARM64 compatible)
- Packages with confirmed ARM64 support in documentation

#### 2. Likely Compatible
- Managed libraries with minimal platform-specific code
- Packages that use only standard .NET APIs
- Libraries that have been tested on ARM64 but lack explicit support statements

#### 3. Requires Verification
- Packages with native dependencies but unclear ARM64 support
- Libraries that use P/Invoke with architecture-specific native libraries
- Database drivers and system-level libraries
- Image processing and multimedia libraries

#### 4. Incompatible
- Packages that explicitly state x64-only support
- Libraries with hardcoded architecture assumptions
- Native libraries compiled only for x64
- Legacy packages without ARM64 builds

### Testing Strategy

#### Build-Time Verification

```bash
# Test build for ARM64
dotnet build -r linux-arm64

# Test publish for ARM64
dotnet publish -r linux-arm64 --self-contained

# Verify package restore
dotnet restore --runtime linux-arm64
```

#### Runtime Testing

```bash
# Create ARM64 container for testing
docker build --platform linux/arm64 -t myapp:arm64 .

# Run on ARM64 hardware
dotnet run --runtime linux-arm64
```

#### Performance Validation

```bash
# Profile ARM64 performance
dotnet run -c Release --runtime linux-arm64

# Compare with x64 baseline
dotnet run -c Release --runtime linux-x64
```

## Common Compatibility Issues and Solutions

### Native Library Dependencies

**Issue**: Application depends on native libraries not available for ARM64

**Solutions**:
- Find ARM64-compatible alternatives
- Use managed implementations where possible
- Contact library maintainers for ARM64 support
- Consider containerization with multi-architecture images

### Platform-Specific Code

**Issue**: Code that assumes x64 architecture or uses x64-specific optimizations

**Solutions**:
- Use `RuntimeInformation.ProcessArchitecture` for architecture detection
- Implement architecture-agnostic algorithms
- Use conditional compilation for architecture-specific code
- Leverage .NET's built-in SIMD support which is architecture-agnostic

### Database Connectivity

**Issue**: Database drivers may not support ARM64

**Solutions**:
- Verify driver ARM64 compatibility
- Use managed database providers where available
- Test connectivity thoroughly on ARM64 hardware
- Consider using connection pooling and retry logic

## Migration Checklist

- [ ] Analyze all project dependencies using `dotnet list package --include-transitive`
- [ ] Identify native library dependencies through P/Invoke analysis
- [ ] Verify target framework compatibility (.NET 6+ recommended)
- [ ] Test build process with `dotnet build -r linux-arm64`
- [ ] Validate package restore for ARM64 runtime
- [ ] Review and test all P/Invoke declarations
- [ ] Performance test on actual ARM64 hardware
- [ ] Update CI/CD pipelines for ARM64 builds
- [ ] Monitor application metrics post-migration
- [ ] Document any architecture-specific considerations

## Troubleshooting Common Issues

### Build Failures

```bash
# Verbose build output for debugging
dotnet build -r linux-arm64 --verbosity detailed

# Check for missing ARM64 packages
dotnet restore --runtime linux-arm64 --verbosity detailed
```

### Runtime Errors

- **BadImageFormatException**: Indicates architecture mismatch between application and native libraries
- **DllNotFoundException**: Native library not found for target architecture
- **PlatformNotSupportedException**: API or feature not supported on ARM64

### Performance Issues

- Profile memory usage patterns on ARM64
- Verify SIMD optimizations are being utilized
- Check for architecture-specific performance regressions
- Monitor garbage collection behavior

## Conclusion

Successful migration of .NET applications to ARM architecture requires a systematic approach to dependency analysis and compatibility assessment. By leveraging the artifacts and tools described in this guide, developers can identify potential compatibility issues early in the migration process and take appropriate remediation steps.

The key to successful ARM migration lies in thorough testing, careful dependency management, and leveraging .NET's built-in cross-platform capabilities. With proper analysis and testing, most .NET applications can achieve excellent performance and compatibility on ARM processors, particularly AWS Graviton instances.

## Resources

- [.NET Runtime Identifier Catalog](https://docs.microsoft.com/en-us/dotnet/core/rid-catalog)
- [AWS Graviton Getting Started Guide](https://github.com/aws/aws-graviton-getting-started)
- [.NET Performance on ARM64](https://devblogs.microsoft.com/dotnet/arm64-performance-in-net-5/)
- [NuGet Package Architecture Support](https://docs.microsoft.com/en-us/nuget/create-packages/supporting-multiple-target-frameworks)