#!/bin/bash
cd ~/defects4j

bugs="Chart-1 Chart-2 Chart-3 Chart-4 Chart-5 Chart-6 Chart-7 Chart-9 Chart-10 Chart-11 Chart-12 Chart-13 Chart-14 Chart-15 Chart-16 Cli-1 Cli-2 Cli-3 Cli-4 Cli-5 Cli-7 Cli-8 Cli-9 Cli-10 Cli-11 Cli-12 Cli-13 Cli-14 Cli-15 Cli-16 Cli-17 Cli-18 Cli-19 Cli-20 Cli-21 Cli-22 Cli-23 Csv-1 Csv-2 Csv-3 Csv-4 Csv-5 Csv-6 Csv-7 Csv-8 Csv-9 Csv-10 Csv-11 Csv-12 Csv-13 Csv-14 Csv-15 Gson-1 Gson-2 Gson-3 Gson-4 Gson-5 Gson-6 Gson-7 Gson-8 Gson-9 Gson-10 Gson-11 Gson-12 Gson-13 Gson-14 Gson-15 Gson-16 Gson-17 Gson-18 JacksonCore-1 JacksonCore-2 JacksonCore-3 JacksonCore-4 JacksonCore-5 JacksonCore-6 JacksonCore-7 JacksonCore-8 JacksonCore-9 JacksonCore-10 JacksonCore-11 JacksonCore-12 JacksonCore-13 JacksonCore-14 JacksonCore-15 JacksonCore-16 JacksonCore-17 JacksonCore-18 JacksonCore-19 JacksonCore-20 JacksonDatabind-1 JacksonDatabind-3 JacksonDatabind-4 JacksonDatabind-5 JacksonDatabind-6 JacksonDatabind-7 JacksonDatabind-8 JacksonDatabind-9 JacksonDatabind-10 JacksonDatabind-11 JacksonDatabind-12 JacksonDatabind-13 JacksonDatabind-14 JacksonDatabind-15 JacksonDatabind-16 Jsoup-1 Jsoup-2 Jsoup-3 Jsoup-4 Jsoup-5 Jsoup-6 Jsoup-7 Jsoup-8 Jsoup-9 Jsoup-10 Jsoup-11 Jsoup-12 Jsoup-13 Jsoup-14 Jsoup-15 Jsoup-16 Lang-1 Lang-3 Lang-4 Lang-5 Lang-6 Lang-7 Lang-8 Lang-9 Lang-10 Lang-11 Lang-12 Lang-13 Lang-14 Lang-15 Lang-16"

echo "{" > ~/root_causes.json
first=true

for entry in $bugs; do
  project=$(echo "$entry" | cut -d'-' -f1)
  bug_num=$(echo "$entry" | cut -d'-' -f2)
  root_cause=$(defects4j info -p "$project" -b "$bug_num" 2>/dev/null | grep -A2 "Root cause" | tail -n1 | sed 's/^ *- *//' | sed 's/"/\\"/g' | tr -d '\n' | tr -d '\r')
  if [ "$first" = true ]; then
    first=false
  else
    printf ',\n' >> ~/root_causes.json
  fi
  printf '  "Defects4J-%s": "%s"' "$entry" "$root_cause" >> ~/root_causes.json
  echo " [$entry done]"
done

printf '\n}\n' >> ~/root_causes.json
echo "Done! File saved to ~/root_causes.json"
