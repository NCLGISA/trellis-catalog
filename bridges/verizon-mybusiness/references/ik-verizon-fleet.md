# Institutional Knowledge: Verizon Wireless Fleet

Last updated: <!-- YYYY-MM-DD -->

## Account Structure

<!-- List your Verizon MyBusiness billing accounts here.
| Account Number | Account Name | Type | Approx Monthly |
|---------------|-------------|------|----------------|
| XXXXXXXXX-XXXXX | Your Organization | Primary wireless | ~$X,XXX |
-->

## Fleet Summary

<!-- Populate after running: python3 fleet_check.py summary
- Total wireless lines: ?
- Active: ?
- Suspended: ?
- 5G capable: ?
- 4G only: ?
- Upgrade eligible: ?
-->

## Device Type Breakdown

### Smartphones
<!-- Populate after running: python3 fleet_check.py by-device-type -->

### ODI / Gateway Devices (AirLink correlation candidates)
<!-- ODI device types power Sierra AirLink gateways in fleet vehicles.
     Subtypes: 4GODINonStationary, 4GODI_Data, 4GODI_D_V, ConnectedDevice -->

### Tablets (Intune iPad correlation candidates)
<!-- Tablets with cellular plans enrolled in Intune.
     Subtypes: 5GTablet, 4GTablet -->

### MiFi Hotspots
<!-- Portable hotspot devices.
     Subtypes: 4GMIFI DEVICE, 5GMIFI DEVICE, 5GHotspot, 4GHotspot -->

### Other
<!-- FeaturePhone, IME, USB Modem, etc. -->

## Cost Center to Department Mapping

<!-- Map your organization's cost center prefixes to department names.
     This mapping is used by fleet_check.py for the by-department command.
     Also update the DEPT_LABELS dict in fleet_check.py.

| Prefix | Department | Lines | Notes |
|--------|-----------|-------|-------|
| XX | Department Name | N | Cost center format: XX-NNNNNNN |
-->

## API Session Parameters

<!-- These values are extracted automatically from session cookies after login.
     Document them here for reference.

| Parameter | Value | Cookie Source |
|-----------|-------|---------------|
| ecpdId | (from profileId cookie) | profileId cookie |
| userId | (your VZ_USERNAME) | VZ_USERNAME env var |
| gon | (from GROUP_ORDER_NUMBER cookie) | GROUP_ORDER_NUMBER cookie |
-->

## Cross-Bridge Correlation Fields

### Fleet list (retrieveEntitledMtn) -- available per-line without extra API call:
- mtn (phone number, dotted format)
- userName
- costCenter
- deviceType
- accountNumber
- status (Active/Suspended)
- simFreezeStatus (Disabled/Enabled)
- eSIMId (True/False)
- planName
- upgradeDate

### Device detail (retrieveMtnDeviceInfo) -- requires per-line API call:
- deviceId (IMEI, 15 digits, right-padded with spaces)
- simId (ICCID, 20 digits)
- equipmentModel (full device name)
- simType4G5G (4G/5G)
- simTypeEsimPsim (eSIM/pSIM)

## Correlation Strategy

### To Sierra AirLink:
1. Filter fleet for ODI + MiFi types
2. Call retrieveMtnDeviceInfo for each to get IMEI
3. Match IMEI against AirLink gateway inventory
4. Expected match rate: ~100% for ODI lines

### To Intune iPads:
1. Filter fleet for Tablet types
2. Match Verizon MTN digits against Intune phoneNumber field
3. Note: Intune phone format may differ from Verizon format -- normalize digits

### Department allocation:
1. Parse cost center prefix
2. Map to department name (see table above)
3. Aggregate by department for reporting
