# Service Loops

Generate **Service Loops** for carrier services.

## Instructions

1. Fetch Service Loop From Carrier APIs/Webpage
```
There are Private/Public APIs/Webpages using for grabbing the service loop from Cosco
```
2.  Convert it to P44 Format

```
Once we get the service loop from carrier, it will be converted to P44 csv format because SCT only can parse P44 csv format
```
3. Load it into KN MFT


4. Finally transfer the csv file to AWS S3 for SeaSchedule

