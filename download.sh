#!/bin/bash

mkdir -p samples
OUTPUT_DIR=samples/


while IFS=, read -r SAMPLE UNUSED
do
    echo ">>> Download sample ${SAMPLE}"
    xrdcp root://eospublic.cern.ch//eos/root-eos/HiggsTauTauReduced/${SAMPLE}.root ${OUTPUT_DIR}
done < metadata.csv
