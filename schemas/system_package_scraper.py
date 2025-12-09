"""
System Package Scraper for generating OS-specific knowledge bases.
Queries OS repositories and generates compatibility data.
"""

import json
import logging
import requests
import re
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path
import defusedxml.ElementTree as ET
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class SystemPackageScraper:
    """Scraper for generating system package knowledge bases from OS repositories."""
    
    def __init__(self, output_dir: str = "."):
        """Initialize scraper with output directory."""
        self.output_dir = Path(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Graviton-Validator-Scraper/1.0'
        })
    
    def scrape_amazon_linux_packages(self, version: str = "2") -> Dict:
        """
        Scrape Amazon Linux package repository.
        
        Args:
            version: Amazon Linux version (2 or 2023)
            
        Returns:
            Dictionary with package information
        """
        logger.info(f"Scraping Amazon Linux {version} packages...")
        
        if version == "2":
            base_url = "https://amazonlinux-2-repos-us-east-1.s3.amazonaws.com/2/core/latest/x86_64/"
            os_name = "amazon-linux-2"
        else:
            base_url = "https://al2023-repos-us-east-1.s3.amazonaws.com/core/latest/x86_64/"
            os_name = "amazon-linux-2023"
        
        packages = []
        
        try:
            # Get repository metadata
            repodata_url = urljoin(base_url, "repodata/repomd.xml")
            response = self.session.get(repodata_url, timeout=30)
            response.raise_for_status()
            
            # Parse repomd.xml to find primary metadata
            root = ET.fromstring(response.content)
            primary_href = None
            
            for data in root.findall('.//{http://linux.duke.edu/metadata/repo}data'):
                if data.get('type') == 'primary':
                    location = data.find('.//{http://linux.duke.edu/metadata/repo}location')
                    if location is not None:
                        primary_href = location.get('href')
                        break
            
            if not primary_href:
                logger.error("Could not find primary metadata in repomd.xml")
                return self._create_empty_kb(os_name)
            
            # Download and parse primary metadata
            primary_url = urljoin(base_url, primary_href)
            logger.info(f"Downloading primary metadata from {primary_url}")
            
            response = self.session.get(primary_url, timeout=60)
            response.raise_for_status()
            
            # Parse XML (handle compressed files)
            content = response.content
            if primary_href.endswith('.gz'):
                import gzip
                content = gzip.decompress(content)
            
            root = ET.fromstring(content)
            
            # Extract package information
            for package in root.findall('.//{http://linux.duke.edu/metadata/common}package'):
                name_elem = package.find('.//{http://linux.duke.edu/metadata/common}name')
                version_elem = package.find('.//{http://linux.duke.edu/metadata/common}version')
                
                if name_elem is not None and version_elem is not None:
                    name = name_elem.text
                    version = version_elem.get('ver', '')
                    release = version_elem.get('rel', '')
                    
                    if name and version:
                        full_version = f"{version}-{release}" if release else version
                        packages.append({
                            "name": name,
                            "version": full_version,
                            "source": "amazon_linux_repo"
                        })
            
            logger.info(f"Found {len(packages)} Amazon Linux {version} packages")
            
        except Exception as e:
            logger.error(f"Error scraping Amazon Linux {version} packages: {e}")
            return self._create_empty_kb(os_name)
        
        return self._create_system_kb(os_name, packages, f"Amazon Linux {version}")
    
    def scrape_ubuntu_packages(self, version: str = "20.04") -> Dict:
        """
        Scrape Ubuntu package repository.
        
        Args:
            version: Ubuntu version (18.04, 20.04, 22.04, etc.)
            
        Returns:
            Dictionary with package information
        """
        logger.info(f"Scraping Ubuntu {version} packages...")
        
        # Map version to codename
        version_codenames = {
            "18.04": "bionic",
            "20.04": "focal", 
            "22.04": "jammy",
            "24.04": "noble"
        }
        
        codename = version_codenames.get(version, "focal")
        base_url = f"http://archive.ubuntu.com/ubuntu/dists/{codename}/"
        
        packages = []
        
        try:
            # Get main component packages
            packages_url = f"{base_url}main/binary-amd64/Packages.gz"
            logger.info(f"Downloading Ubuntu packages from {packages_url}")
            
            response = self.session.get(packages_url, timeout=60)
            response.raise_for_status()
            
            # Decompress and parse packages file
            import gzip
            content = gzip.decompress(response.content).decode('utf-8')
            
            current_package = {}
            for line in content.split('\n'):
                if line.startswith('Package: '):
                    if current_package.get('name'):
                        packages.append({
                            "name": current_package['name'],
                            "version": current_package.get('version', ''),
                            "source": "ubuntu_repo"
                        })
                    current_package = {'name': line[9:].strip()}
                elif line.startswith('Version: '):
                    current_package['version'] = line[9:].strip()
                elif line == '':  # Empty line indicates end of package
                    if current_package.get('name'):
                        packages.append({
                            "name": current_package['name'],
                            "version": current_package.get('version', ''),
                            "source": "ubuntu_repo"
                        })
                        current_package = {}
            
            # Don't forget the last package
            if current_package.get('name'):
                packages.append({
                    "name": current_package['name'],
                    "version": current_package.get('version', ''),
                    "source": "ubuntu_repo"
                })
            
            logger.info(f"Found {len(packages)} Ubuntu {version} packages")
            
        except Exception as e:
            logger.error(f"Error scraping Ubuntu {version} packages: {e}")
            return self._create_empty_kb("ubuntu")
        
        return self._create_system_kb("ubuntu", packages, f"Ubuntu {version}")
    
    def generate_system_package_kb(self, os_configs: Dict) -> Dict:
        """
        Generate comprehensive system package knowledge base.
        
        Args:
            os_configs: OS configuration data
            
        Returns:
            Complete system package knowledge base
        """
        logger.info("Generating comprehensive system package knowledge base...")
        
        system_kb = {
            "$schema": "./system_packages_schema.json",
            "metadata": {
                "version": "1.0",
                "description": "System packages for Graviton-compatible operating systems",
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "maintainer": "System Package Scraper",
                "notes": "Auto-generated from OS repositories and static data"
            },
            "system_packages": {}
        }
        
        # Add scraped packages for each OS
        for os_name, os_info in os_configs.get("supported_operating_systems", {}).items():
            if not os_info.get("graviton_compatible", False):
                continue
            
            logger.info(f"Processing system packages for {os_name}...")
            
            # Create system package entry
            system_packages = {
                "graviton_compatible": True,
                "package_types": os_info.get("package_types", []),
                "detection_patterns": os_info.get("package_patterns", []),
                "vendor_names": os_info.get("vendor_names", []),
                "common_packages": self._get_common_packages(os_name),
                "kernel_modules": self._get_kernel_modules(os_name),
                "system_libraries": self._get_system_libraries(os_name)
            }
            
            system_kb["system_packages"][os_name] = system_packages
        
        return system_kb
    
    def _get_common_packages(self, os_name: str) -> List[str]:
        """Get list of common system packages for an OS."""
        common_packages = {
            "amazon-linux-2": [
                "kernel", "glibc", "bash", "coreutils", "systemd", "rpm", "yum",
                "openssh", "openssl", "curl", "wget", "tar", "gzip", "sed", "grep",
                "awk", "vim", "nano", "less", "which", "findutils", "procps-ng"
            ],
            "amazon-linux-2023": [
                "kernel", "glibc", "bash", "coreutils", "systemd", "rpm", "dnf",
                "openssh", "openssl", "curl", "wget", "tar", "gzip", "sed", "grep",
                "awk", "vim", "nano", "less", "which", "findutils", "procps-ng"
            ],
            "ubuntu": [
                "linux-image", "libc6", "bash", "coreutils", "systemd", "dpkg", "apt",
                "openssh-client", "openssl", "curl", "wget", "tar", "gzip", "sed", "grep",
                "gawk", "vim", "nano", "less", "debianutils", "findutils", "procps"
            ],
            "rhel": [
                "kernel", "glibc", "bash", "coreutils", "systemd", "rpm", "yum",
                "openssh", "openssl", "curl", "wget", "tar", "gzip", "sed", "grep",
                "gawk", "vim", "nano", "less", "which", "findutils", "procps-ng"
            ],
            "debian": [
                "linux-image", "libc6", "bash", "coreutils", "systemd", "dpkg", "apt",
                "openssh-client", "openssl", "curl", "wget", "tar", "gzip", "sed", "grep",
                "gawk", "vim", "nano", "less", "debianutils", "findutils", "procps"
            ]
        }
        
        return common_packages.get(os_name, [])
    
    def _get_kernel_modules(self, os_name: str) -> List[str]:
        """Get list of common kernel modules for an OS."""
        return [
            "ext4", "xfs", "btrfs", "nfs", "cifs", "fuse",
            "ip_tables", "netfilter", "bridge", "vlan",
            "tcp_bbr", "tcp_cubic", "udp", "sctp",
            "kvm", "virtio", "xen", "vmware",
            "usb_storage", "sd_mod", "sr_mod", "cdrom",
            "e1000", "e1000e", "igb", "ixgbe", "virtio_net"
        ]
    
    def _get_system_libraries(self, os_name: str) -> List[str]:
        """Get list of common system libraries for an OS."""
        return [
            "glibc", "libssl", "libcrypto", "libz", "libm", "libdl",
            "libpthread", "librt", "libutil", "libc", "libgcc",
            "libstdc++", "libgomp", "libquadmath", "libatomic",
            "systemd", "dbus", "udev", "polkit", "networkmanager"
        ]
    
    def _create_system_kb(self, os_name: str, packages: List[Dict], description: str) -> Dict:
        """Create system package knowledge base entry."""
        return {
            "os_name": os_name,
            "description": description,
            "package_count": len(packages),
            "packages": packages[:1000],  # Limit to first 1000 packages
            "generated_date": datetime.now().isoformat()
        }
    
    def _create_empty_kb(self, os_name: str) -> Dict:
        """Create empty knowledge base entry."""
        return {
            "os_name": os_name,
            "description": f"Empty knowledge base for {os_name}",
            "package_count": 0,
            "packages": [],
            "generated_date": datetime.now().isoformat()
        }
    
    def save_knowledge_base(self, kb_data: Dict, filename: str) -> None:
        """Save knowledge base to JSON file."""
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(kb_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved knowledge base to {output_path}")
    
    def scrape_all_supported_os(self, os_config_file: str) -> None:
        """
        Scrape packages for all supported operating systems.
        
        Args:
            os_config_file: Path to OS configuration file
        """
        logger.info("Starting comprehensive OS package scraping...")
        
        # Load OS configuration
        with open(os_config_file, 'r', encoding='utf-8') as f:
            os_config = json.load(f)
        
        # Generate system package knowledge base
        system_kb = self.generate_system_package_kb(os_config)
        self.save_knowledge_base(system_kb, "system_packages_generated.json")
        
        # Scrape specific OS repositories (examples)
        scraped_data = {}
        
        # Amazon Linux 2
        try:
            amzn2_kb = self.scrape_amazon_linux_packages("2")
            scraped_data["amazon-linux-2"] = amzn2_kb
            self.save_knowledge_base(amzn2_kb, "amazon_linux_2_packages.json")
        except Exception as e:
            logger.error(f"Failed to scrape Amazon Linux 2: {e}")
        
        # Ubuntu 20.04
        try:
            ubuntu_kb = self.scrape_ubuntu_packages("20.04")
            scraped_data["ubuntu-20.04"] = ubuntu_kb
            self.save_knowledge_base(ubuntu_kb, "ubuntu_20_04_packages.json")
        except Exception as e:
            logger.error(f"Failed to scrape Ubuntu 20.04: {e}")
        
        # Create combined knowledge base
        combined_kb = {
            "metadata": {
                "version": "1.0",
                "description": "Combined system package data from multiple OS repositories",
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "maintainer": "System Package Scraper"
            },
            "system_packages": system_kb["system_packages"],
            "scraped_repositories": scraped_data
        }
        
        self.save_knowledge_base(combined_kb, "combined_system_packages.json")
        logger.info("Completed comprehensive OS package scraping")


def main():
    """Main function for running the scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(description="System Package Scraper for Graviton Validator")
    parser.add_argument("--config", "-c", default="graviton_os_compatibility.json",
                       help="Path to OS configuration file")
    parser.add_argument("--output", "-o", default=".",
                       help="Output directory for generated files")
    parser.add_argument("--os", choices=["amazon-linux-2", "amazon-linux-2023", "ubuntu"],
                       help="Scrape specific OS only")
    parser.add_argument("--version", default="2",
                       help="OS version to scrape (for Amazon Linux: 2 or 2023, for Ubuntu: 18.04, 20.04, etc.)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = SystemPackageScraper(args.output)
    
    if args.os:
        # Scrape specific OS
        if args.os == "amazon-linux-2":
            kb = scraper.scrape_amazon_linux_packages(args.version)
            scraper.save_knowledge_base(kb, f"amazon_linux_{args.version}_packages.json")
        elif args.os == "amazon-linux-2023":
            kb = scraper.scrape_amazon_linux_packages("2023")
            scraper.save_knowledge_base(kb, "amazon_linux_2023_packages.json")
        elif args.os == "ubuntu":
            kb = scraper.scrape_ubuntu_packages(args.version)
            scraper.save_knowledge_base(kb, f"ubuntu_{args.version.replace('.', '_')}_packages.json")
    else:
        # Scrape all supported OS
        scraper.scrape_all_supported_os(args.config)


if __name__ == "__main__":
    main()