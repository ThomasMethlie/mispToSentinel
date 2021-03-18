# mispToSentinel
Pull data from MISP and send to MS Sentinel via Graph API

# based on
https://github.com/microsoftgraph/security-api-solutions/tree/master/Samples/MISP

## changes made from original source
* read complex MISP events that contains related events
* read MISP config from command line to be able to support pulling data from multiple MISP servers
