from configparser import ConfigParser
from pathlib import Path

# Path to your setup.cfg and requirements.txt files
setup_cfg_path = Path("setup.cfg")
requirements_txt_path = Path("requirements.txt")

# Read requirements.txt and extract the packages
with requirements_txt_path.open("r") as file:
    requirements = file.readlines()
    requirements = [
        req.strip()
        for req in requirements
        if req.strip() and not req.startswith("#")
    ]

# Load the existing setup.cfg
config = ConfigParser()
config.read(setup_cfg_path)

# Update install_requires in setup.cfg
config["options"]["install_requires"] = "\n    ".join(requirements)

# Save the updated setup.cfg
with setup_cfg_path.open("w") as configfile:
    config.write(configfile)
