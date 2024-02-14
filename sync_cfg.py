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

# Prepare the formatted string for install_requires, ensuring correct
# indentation. The first requirement starts on the same line, so it's
# not indented.
install_requires_formatted = "\n".join(
    requirements
)  # Adjusted indentation here if needed

# In case there are no requirements, avoid adding the section
if requirements:
    if "options" not in config:
        config["options"] = {}
    config.set(
        "options", "install_requires", install_requires_formatted
    )
else:
    # Handle the case where there are no install_requires to specify
    if "options" in config and "install_requires" in config["options"]:
        config.remove_option("options", "install_requires")

# Save the updated setup.cfg
with setup_cfg_path.open("w") as configfile:
    config.write(configfile)
