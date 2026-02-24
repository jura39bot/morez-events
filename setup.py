from setuptools import setup, find_packages

setup(
    name="morez-events",
    version="0.1.0",
    description="Rapport hebdomadaire des événements culturels et sportifs autour de Morez (Jura)",
    author="Mathieu Chevalier",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.31",
        "beautifulsoup4>=4.12",
        "lxml>=4.9",
        "typer[all]>=0.9",
        "rich>=13.0",
        "python-dateutil>=2.8",
    ],
    entry_points={
        "console_scripts": [
            "morez-events=morez_events.cli:main",
        ],
    },
)
