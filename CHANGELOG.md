# Changelog

## [1.0.1] - 2026-08-01

### Changed
- Repository renamed from `hacs-timebutler` to `timebutler`. The `documentation` and `issue_tracker` URLs in the manifest now point to the new location.

## [1.0.0] - 2026-04-18

### Added
- Initial release
- Individual user sensors showing current status (working, paused, vacation, sick, off, and all Timebutler absence types)
- Group sensors counting people working and on break
- Per-department group sensors
- Dynamic sensors for each absence type returned by the API
- UI-based configuration flow with API token validation
- Configurable polling interval (1–60 minutes, default 5 minutes)
- English and German translations
- Parallel timeclock fetching with concurrency limit
