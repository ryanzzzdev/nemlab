
# Misc TODOs manually maintained by the user

Should the backend get all the data available in OpenEletricity API, regardless we need or not? 


#
cd nemlab
set -a; . ./.env; set +a
./gradlew :worker:bootRun
./gradlew :api:bootRun
