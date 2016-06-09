# Sanergy: Sanitation in Nairobi, Kenya
Repository for 2016 DSSG project with Sanergy
### Input data files and instructions
##### "IPA/IPA_data_incomplete.sav" (SPSS)
###### Setup
Using **R** and specifically the *foreign* package, the .sav file was converted to .csv and then uploaded to the postgres database. Example:
```R
library(foreign)
sav_data <- read.spss('../IPA/IPA_data_incomplete.sav');
write.csv(sav_data, '../IPA/IPA_data_incomplete.csv');
```
###### Description
##### "Waste Data January 22 2015 - January 22 2016.xlsx" (Excel)
##### "Sanergy - Fresh Life Toilet Waste DataBase.bak" (MS SQL Server)
###### Setup
See **Joe Walsh** about spinning up a MS SQL Server, installing the backup file, restoring it, and uploading it to the postgres server.
###### Description
The .bak file includes 10 data tables, the following describes their shape (rows, columns) and what we perceive as unique identifiers.
* Collection_Data__c (522,263 rows, ):
* FLT_Collection_Schedule__c
* _IPA_tbl_system_user
* _IPA_tbl_toilet
* _IPA_tbl_transactions
* _IPA_tbl_user
* _IPA_tbl_user_card
* spatial_ref_sys
* stdin
* tblToilet
##### "Map Kibera/Shapefiles" (Shapefiles)
