# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0]

### Added

- Taskbar icon hiding for cleaner desktop widget experience (Windows only)


## [1.0.0]

### Added

- Initial release of Data Trakr desktop widget
- Real-time network data usage tracking (sent/received/total)
- Hourly usage bar chart visualization
- Persistent data storage across application restarts
- Always-on-top floating window with opacity effects
- Notification system for data consumption thresholds
- VS Code build task using Flet pack
- MIT license
- Documentation and changelog

### Technical Details

- Built with Flet framework for cross-platform desktop apps
- Uses psutil for network monitoring
- Data stored in JSON format
- PyInstaller packaging for standalone executable
- Tested on Windows 11 platform
