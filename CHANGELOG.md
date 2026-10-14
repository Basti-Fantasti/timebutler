# Changelog

## [1.1.0] - 2026-10-14

### Added
- User sensors expose `absence_half_day` and `absence_morning` for the current absence. Automations can use them to tell half-day absences from full-day absences.

### Changed
- Minimum Home Assistant version raised from 2023.1.0 to 2024.12.0. The integration uses `single_config_entry`, `ConfigFlowResult` and the options flow without an explicit `config_entry`. The test suite fails on 2024.11.0 and passes on 2024.12.0.

### Security
- The config entry unique ID is now a SHA-256 hash of the API token. Earlier versions stored the first 16 characters of the token, which appeared in diagnostics and debug output.
- Existing entries migrate to the hashed unique ID on the first start after the update (config entry version 1.2). Entity IDs do not change.

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
- Configurable polling interval (1 to 60 minutes, default 5 minutes)
- English and German translations
- Parallel timeclock fetching with concurrency limit
