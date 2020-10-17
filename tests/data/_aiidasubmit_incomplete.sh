#!/bin/bash -l
#$ -cwd
#$ -S /bin/bash
#$ -m n
#$ -N aiida-340981
#$ -o _scheduler-stdout.txt
#$ -e _scheduler-stderr.txt
#$ -l h_rt=08:00:00
#$ -l mem=4G


#$ -P Gold
#$ -A Faraday_FCAT

module unload compilers mpi
module load compilers/intel/2017/update1
module load mpi/intel/2017/update1/intel

#$ -ac allow=K

'gerun' '/shared/ucl/apps/vasp/5.4.4-18apr2017/intel-2017/bin/vasp_std'