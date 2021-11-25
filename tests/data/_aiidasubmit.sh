#!/bin/bash -l
#$ -N aiida-340981
#$ -o _scheduler-stdout.txt
#$ -e _scheduler-stderr.txt
#$ -pe mpi 24
#$ -l h_rt=08:00:00

module unload compilers mpi
module load compilers/intel/2017/update1
module load mpi/intel/2017/update1/intel

'gerun' '/shared/ucl/apps/vasp/5.4.4-18apr2017/intel-2017/bin/vasp_std'