# grade.py
#
# usage:
#   python grade.py MainClass TestDir [--outpre outfilePrefix] [--inext infileExt] [--gradescope]
#
# usage examples:
#   python grade.py Section2Binary PublicTestCases --outpre binary 
#
# This grade.py is attempting to be more general for 
# programs that accept command line input in addition
# to or other than an input file name.  It assumes that
# the output files in the given test directory end in .out.
# It will then look for all outfiles with the given prefix.
# After the prefix each command line option should be provided
# in the outfile name separated by dashes.  The input file
# if there is one will be provided without an extension.  The
# optional argument to the grade script will be the infile extension
# if the first command line option is a file.
#
# examples:
#   binary-5.out
#       The output prefix is "binary".  The program will be run with
#       the command line "5".
#
#   python grade.py --mainclass PA2Main --testdir PublicTestCases --outpre pa2 --inext csv
#   outfile: pa2-miniRoutes-MAX.out
#       If I were going to redo the PA2 testing, this is what to do.
#       In this one the output prefix is "pa2".
#       Command line args: miniRoutes.csv MAX
#

# If the gradescope options is specified then the source
# code will be found in "/autograder/submission/".
# The script always generates a TestingTemp/results.json 
# file that could be used by gradescope.
#
# Another assumption is that all of the source files are in the 
# default package and are in the src/ subdirectory.
# And the actual testing will happen in the testdir.
# Also assuming the correctness grade is out of 50 points.
import argparse
import sys
import os
import json
import subprocess
import glob
from functools import reduce
import shutil

#######################################
# global variables
tempdir = "TestingTemp/"
totalpoints = 50.0
gradescope_outfile = "results.json"


def getSubmissionSource(gradescope_flag):
#######################################
# like global variables should be set by user
    if gradescope_flag:
        return "/autograder/submission/"
    else:
        return "src/"


def cmdLineParse(argv):
#######################################
# Returns an args class with gradescope, mainclass, testdir, inext, and outpre specified.
    parser = argparse.ArgumentParser(description="grading script for CS 210")
    parser.add_argument('mainclass')
    parser.add_argument('testdir')
    parser.add_argument('--outpre', help='Prefix for expected outfiles.')
    parser.add_argument('--inext', help='Extention for input files.')
    parser.add_argument('--gradescope', help='Copy submission from gradescope location.',
            action="store_true")
    #DEBUG: parser.print_help()
    args = parser.parse_args()
    #DEBUG: print(args)
    return args


def copySrcToTempAndCDThere(srcdir, tempdir):
#######################################
# Copying over all the source files into the testing
# directory, clean the directory, and then move into that directory.
# First parameter should be the source directory path.
# Second parameter should be the temporary directory.

    # force the removal of tempdir
    if (os.path.exists(tempdir)):
        shutil.rmtree(tempdir)

    # If the temporary directory doesn't already exist make it.
    #if not os.path.exists(tempdir):
    os.makedirs(tempdir)

    # copy the source code over and move into directory
    os.system("cp "+srcdir+"/*.java "+tempdir)
    os.chdir (tempdir)

def execCommand(commandstr):
#######################################
# execute the given unix command line
# if successful then will return (0,stdout)
# if error then will return (cmdretcode,stderr)
# commandstr should be something like 'javac PA2Main.java'
# 
# reference for this code
# https://stackoverflow.com/questions/16198546/get-exit-code-and-stderr-from-subprocess-call
    retcode = 0
    try:
        output = subprocess.check_output(
            commandstr, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError as exc:
        output = exc.output
        retcode = exc.returncode

    return (retcode,output)


def truncateFloats(infile,outfile):
#######################################
# Will truncate all of the floating points to 2 decimal
# places and place the new version of the file in the
# given output file.
    execCommand("perl -pe 's/[-+]?\d*(?:\.?\d|\d\.)" \
                +"\d*(?:[eE][-+]?\d+)?/sprintf(\"%.2f\",$&)/ge' " \
                +infile+" > "+outfile)



def formatFloat(inval):
#######################################
# Want floats in our score output to all have 2 decimal points
    return float("%.2f" % inval)

def createTestRecord(mainclassname,expected_output_file,
                     cmd_str,max_grade_per_test):
#######################################
# create a test record for each test
# run the program and redirect to the "out" file
# will compare with the given expected_output_file

    # run the program
    run_cmd = "java "+mainclassname+ " "+ cmd_str+" > out"
    (run_retcode,run_output) = execCommand(run_cmd)

    # do a diff with the generated output and the expected output
    diff_cmd = "diff -B -w out "+expected_output_file
    (diff_retcode,diff_output) = execCommand(diff_cmd)
        
    # put together all the information in the test record
    if diff_retcode!=0:
        score = 0.0
        mesg = "Failed " + expected_output_file + " test.\n" \
               + "*********** DIFF OUTPUT: Actual output followed by expected.\n"
        print(mesg+diff_output)
    else:
        score = max_grade_per_test
        mesg = "Passed " + expected_output_file + " test.\n"
        print(mesg)

    return { "score"       : formatFloat(score),
             "max_score"   : formatFloat(max_grade_per_test),
             "name"        : expected_output_file,
             "output"      : mesg + diff_output }


def compileProgram(mainclassname):
#######################################
# try to compile the program
# return (boolean indicating if succeeded, output message)

    # do the compile
    compile_cmd = 'javac '+mainclassname+'.java'
    (retcode,output) = execCommand(compile_cmd)

    # If compilation failed
    mesg_prefix = 'Compilation (' + compile_cmd + ')'
    if retcode!=0:
        print(mesg_prefix+' FAILED:\n'+output)
        return (False,mesg_prefix+' FAILED:\n'+output)
    else:
        print(mesg_prefix+' SUCCEEDED!\n')
        return (True,mesg_prefix+' SUCCEEDED!\n')


def parseOutFileName(outfile,outpre,infile_path,infile_ext):
#######################################
# outfile is the outfile name in format discussed in above file header.
# outpre is the outfile prefix.  Assuming not passed in if doesn't match.
# infile_ext is None if there is no infile and a string if the first
#   command line argument is an infile that needs an extension.
#    
# returns command str for use as command line arguments for program
#
# assumming names are in format outpre-infilebase-other-cmd-args.out
# or outpre-cmd-args.out if there won't be an infile
    #print("DEBUG: outfile=",outfile)
    # take off the out extension
    outfile = outfile[0:-4]

    # outpre will now be followed by cmd line args
    cmd_line_parts = outfile.split('-')
    if (cmd_line_parts[0]!=outpre):
        print("grade.py ERROR: file_name_parts[0]!=outpre")
        sys.exit()
    cmd_line_parts.pop(0)

    # see if we need to grab an infile base
    if (infile_ext!=None):
        cmd_line_parts[0] = infile_path + cmd_line_parts[0] + "." + infile_ext
    # concat all the command line arguments with spaces between
    cmd_str = reduce(lambda a,b: a+" "+b, cmd_line_parts, "")
    #print("DEBUG: cmd_str=",cmd_str)
   
    return cmd_str


def runTests(mainclassname,testdir,outpre,inext):
#######################################
# returns (list of test records,total_score,failed_at_least_once flag)

    # get a list of all the output files and max score per test
    output_files = glob.glob("../"+testdir+"/"+outpre+"*.out")
    max_grade_per_test = totalpoints/float(len(output_files))

    # Do all of the tests
    test_records = []
    total_score = 0.0
    failed_at_least_once = False
    for outfile in output_files:
        cmd_str = parseOutFileName(os.path.basename(outfile),outpre,
                                   "../"+testdir+"/",inext)
        test_rect = createTestRecord(mainclassname, outfile, cmd_str,
                                     max_grade_per_test)
        failed_at_least_once = failed_at_least_once \
                               or (test_rect["score"]==0)
        total_score = total_score + test_rect["score"]
        test_records.append(test_rect)

    return (test_records, total_score, failed_at_least_once)



#######################################
# main python routine

# set everything up and cd into temporary directory
args = cmdLineParse(sys.argv)
srcdir = getSubmissionSource(args.gradescope)
copySrcToTempAndCDThere(srcdir, tempdir)

# see https://gradescope-autograders.readthedocs.io/en/latest/specs/
# for format of json file that will come from results_dict
results_dict = {}

#### try to compile the program
(compile_succeeded,compile_msg) = compileProgram(args.mainclass)
results_dict["output"] = compile_msg

#### If compilation failed then done, else do testing
if (compile_succeeded):
    (test_records, total_score, failed_at_least_once) \
            = runTests(args.mainclass,args.testdir,args.outpre,args.inext)
    results_dict["score"] = round(formatFloat(total_score))
    results_dict["tests"] = test_records
else:
    results_dict["score"] = 0.0
    failed_at_least_once = True

# Testing output to stdout and the results.json file
print("score = "+str(results_dict["score"])+" out of "+str(totalpoints))
results_file = open(gradescope_outfile,"w")
json=json.dumps(results_dict, sort_keys=True, indent=4, separators=(',', ': '))
results_file.write(json)
results_file.close()

# Indicate whether there were any failures
if failed_at_least_once:
    sys.exit(1)
else:
    sys.exit(0)
