#! /bin/csh -f


echo ' #---------------------------------------------------------------'
echo '            Script to Generate Re-gridded ERA5 files'
echo ' #---------------------------------------------------------------'

#===================================================================
# CONFIGRATION SECTION:
#===================================================================
module load ncl

# Set a REFERENCE (Starting) Date and the numbe rof days to process
#-------------------------------------------------------------------
# set RUNNUM   = 01
# set REF_DATE = '20160102'
# set NUM_DAYS = 3


# Check if a command line argument was provided
if ($#argv >= 1) then
    set input_date = $1
else
    # If no argument was provided, ask for it interactively
    echo ' '; echo -n "Please enter the date (YYYYMMDD): "
    set input_date = "$<"
endif

# Ensure the variable is exactly 8 characters long to prevent the GNU 'date' bug!
set len = `echo "$input_date" | awk '{print length($0)}'`
if ($len != 8) then
    echo "Error: Date must be exactly 8 digits (YYYYMMDD)."
    exit 1
endif

# Extract components
set year = `echo $input_date | cut -c1-4`
set month = `echo $input_date | cut -c5-6`

# Set variables
set RUNNUM = $month
set REF_DATE = $input_date

# Get number of days using date command (if available)
set NUM_DAYS = `date -d "${year}-${month}-01 +1 month -1 day" +%d`

echo "RUNNUM   = $RUNNUM"
echo "REF_DATE = '$REF_DATE'"
echo "year     = $year"
echo "month    = $month"
echo "NUM_DAYS = $NUM_DAYS"

# Set INPUT/OUTPUT/TMP directories,
#-----------------------------------
set NAMELIST = './Config/Config_makeIC-'$RUNNUM'.nl'
set MYLOGDIR  = './LOG/LOG_001.'$RUNNUM'/'
set MYTMPDIR  = './TMP/TMP_001.'$RUNNUM'/'
set MYOUTDIR  = '/glade/derecho/scratch/tvmora/tmp/'
set INPUTDIR  = '/gdex/data/d633006/'


# Set Clean option
#------------------------
set TMP_clean   = 'True'

# Set Processing options
#------------------------
set CASE                   = 'ERA5_fv09'
set DYCORE                 = 'fv'
set PRECISION              = 'float'
set VORT_DIV_TO_UV         = 'False'
set SST_MASK               = 'False'
set ICE_MASK               = 'False'
set OUTPUT_PHIS            = 'True'
set REGRID_ALL             = 'False'
set ADJUST_STATE_FROM_TOPO = 'True'

# Set files containig OUTPUT Grid structure and topography
#---------------------------------------------------------
set fname_grid_info        = '/glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/inic/fv/cami-mam3_0000-01-01_0.9x1.25_L30_c100618.nc'
set fname_phis_output      = '/glade/campaign/cesm/cesmdata/cseg/inputdata/atm/cam/topo/fv_0.9x1.25_nc3000_Nsw042_Nrs008_Co060_Fi001_ZR_160505.nc'
set ftype_phis_output      = 'FV_TOPOGRAPHY'

# Set INPUT filename format, type of file, and number of time records per file
#------------------------------------------------------------------------------
set fname   = ( none none none none none none )
set ftype   = ( none none none none none none )
set ftime   = ( none none none none none none )
set hoursec = ( 00000 03600 07200 10800 14400 18000 21600 25200 28800 32400 36000 39600 43200 46800 50400 54000 57600 61200 64800 68400 72000 75600 79200 82800)
set hourstr = (   00    01    02    03    04    05    06    07    08    09    10    11    12    13    14    15    16    17    18    19    20    21    22    23 )
set hourstr0= (   00    00    00    00    00    00    06    06    06    06    06    06    12    12    12    12    12    12    18    18    18    18    18    18 )
set hourstr1= (   05    05    05    05    05    05    11    11    11    11    11    11    17    17    17    17    17    17    23    23    23    23    23    23 )
set fname[1] = "e5.oper.an.ml/YYYYMM/e5.oper.an.ml.0_5_0_0_0_t.regn320sc.YYYYMMDDHH_YYYYMMDDXX.nc"
set ftype[1] = "ERA5_T"
set ftime[1] = "1X"
set fname[2] = "e5.oper.an.ml/YYYYMM/e5.oper.an.ml.0_5_0_2_2_u.regn320uv.YYYYMMDDHH_YYYYMMDDXX.nc"
set ftype[2] = "ERA5_U"
set ftime[2] = "1X"
set fname[3] = "e5.oper.an.ml/YYYYMM/e5.oper.an.ml.0_5_0_2_3_v.regn320uv.YYYYMMDDHH_YYYYMMDDXX.nc"
set ftype[3] = "ERA5_V"
set ftime[3] = "1X"
set fname[4] = "e5.oper.an.ml/YYYYMM/e5.oper.an.ml.128_134_sp.regn320sc.YYYYMMDDHH_YYYYMMDDXX.nc"
set ftype[4] = "ERA5_PS"
set ftime[4] = "1X"
set fname[5] = "e5.oper.an.ml/YYYYMM/e5.oper.an.ml.0_5_0_1_0_q.regn320sc.YYYYMMDDHH_YYYYMMDDXX.nc"
set ftype[5] = "ERA5_Q"
set ftime[5] = "1X"
set fname[6] = "e5.oper.invariant/e5.oper.invariant.128_129_z.regn320sc.2016010100_2016010100.nc"
set ftype[6] = "ERA5_Z"
set ftime[6] = "1X"

# Set the OUTPUT fileds and the index of the file containing them
#------------------------------------------------------------------
set fields       = ( U V T PS Q US VS)
set field_findex = ( 2 3 1 4  5 2  3)

# Set the index of the file containing the INPUT topography
#------------------------------------------------------------------
set phis_findex  = 6


#===================================================================
# PROCESSING SECTION:
#   Loop over range of times,
#   generate inpute namelist for each time,
#   then generate the desired Nudging data
#===================================================================

# Construct the fields string
#-----------------------------
set fieldstr  = $fields[1]
set jj        = $field_findex[1]
@ jj = $jj - 1
set findexstr = $jj
set ii = 1
set fnum = $#fields
while( $ii <  $fnum )
  @ ii = $ii + 1
  set jj = $field_findex[$ii]
  @ jj = $jj - 1
  set fieldstr  = `echo $fieldstr','$fields[$ii]`
  set findexstr = `echo $findexstr','$jj`
end

set jj = $phis_findex
@ jj = $jj - 1
set phisstr = $jj

# Build NCL fortran library
#---------------------------
#/usr/local/bin/WRAPIT         MAKEIC.stub MAKEIC.f90
#/contrib/ncl-6.1.0/bin/WRAPIT MAKEIC.stub MAKEIC.f90
#WRAPIT MAKEIC.stub MAKEIC.f90
/glade/u/apps/opt/ncl/6.6.2/bin/WRAPIT MAKEIC.stub MAKEIC.f90

#
# Loop over range of times to process
#  For the first time true, force
#  generation of ESMF weight datasets
#=====================================
set NDAYS = 0
while ( $NDAYS < $NUM_DAYS )

  # Set current time values
  #------------------------
  set Yearstr = "`date --date=$REF_DATE+${NDAYS}day +%Y`"
  set Monstr  = "`date --date=$REF_DATE+${NDAYS}day +%m`"
  set Daystr  = "`date --date=$REF_DATE+${NDAYS}day +%d`"
  #echo $Yearstr ' / ' $Monstr ' / ' $Daystr

  # Loop over the hourly values (24X daily)
  #========================================
  foreach hnum ( 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 )

    # Set Values dependend upon $hnum, clean
    # up TMP files at the end of each DAY
    #----------------------------------------------------------------------
    set datestr = $Yearstr$Monstr$Daystr$hoursec[$hnum]
    set LOGFILE = $MYLOGDIR'/LogNCL.'$Yearstr$Monstr$Daystr$hoursec[$hnum]
    if( $hnum == 24 ) then
      set TMP_clean   = 'True'
    else
      set TMP_clean   = 'False'
    endif

    echo $Yearstr ' / ' $Monstr ' / ' $Daystr ' ' $hoursec[$hnum]

    # Create Namelist file for current time
    #----------------------------------------
    echo '                                       '             > $NAMELIST
    echo '! Generated Namelist for maekIC_se.ncl '            >> $NAMELIST
    echo '!-------------------                   '            >> $NAMELIST
    echo '&makeic_nl'                                         >> $NAMELIST
    echo ' MYTMPDIR="'$MYTMPDIR'"'                            >> $NAMELIST
    echo ' MYOUTDIR="'$MYOUTDIR'"'                            >> $NAMELIST
    echo ' INPUTDIR="'$INPUTDIR'"'                            >> $NAMELIST
    echo '                                    '               >> $NAMELIST
    echo ' TMP_clean  ="'$TMP_clean'"'                        >> $NAMELIST
    echo '                                    '               >> $NAMELIST
    echo ' REF_DATE              ="'$REF_DATE'"'              >> $NAMELIST
    echo ' CASE                  ="'$CASE'"'                  >> $NAMELIST
    echo ' DYCORE                ="'$DYCORE'"'                >> $NAMELIST
    echo ' PRECISION             ="'$PRECISION'"'             >> $NAMELIST
    echo ' VORT_DIV_TO_UV        ="'$VORT_DIV_TO_UV'"'        >> $NAMELIST
    echo ' SST_MASK              ="'$SST_MASK'"'              >> $NAMELIST
    echo ' ICE_MASK              ="'$ICE_MASK'"'              >> $NAMELIST
    echo ' OUTPUT_PHIS           ="'$OUTPUT_PHIS'"'           >> $NAMELIST
    echo ' REGRID_ALL            ="'$REGRID_ALL'"'            >> $NAMELIST
    echo ' ADJUST_STATE_FROM_TOPO="'$ADJUST_STATE_FROM_TOPO'"'>> $NAMELIST
    echo '                                    '               >> $NAMELIST
    echo ' fname_phis_output     ="'$fname_phis_output'"'     >> $NAMELIST
    echo ' ftype_phis_output     ="'$ftype_phis_output'"'     >> $NAMELIST
    echo ' fname_grid_info       ="'$fname_grid_info'"'       >> $NAMELIST
    echo '                                    '               >> $NAMELIST
    echo ' fields       ="'$fieldstr'"'                       >> $NAMELIST
    echo ' source_files ="'$findexstr'"'                      >> $NAMELIST
    echo ' fname_phis_in='$phisstr                            >> $NAMELIST
    echo '                                    '               >> $NAMELIST
    set ii = 0
    set fnum = $#fname
    while( $ii <  $fnum )
      set jj = $ii
      @ ii = $ii + 1
      set file = $fname[$ii]
      set file = `echo $file | sed 's/YYYY/'$Yearstr'/g'`
      set file = `echo $file | sed 's/MM/'$Monstr'/g'`
      set file = `echo $file | sed 's/DD/'$Daystr'/g'`
      if( $ftime[$ii] == "4X" ) then
        set file = `echo $file | sed 's/HH/'$hourstr[1]'/'`
        set file = `echo $file | sed 's/HH/'$hourstr[4]'/'`
      else
        set file = `echo $file | sed 's/HH/'$hourstr0[$hnum]'/g'`
	set file = `echo $file | sed 's/XX/'$hourstr1[$hnum]'/g'`
      endif
      echo " fname$jj="'"'$file'"'                      >> $NAMELIST
    end
    echo '                                    '               >> $NAMELIST
    set ii = 0
    set fnum = $#fname
    while( $ii <  $fnum )
      set jj = $ii
      @ ii = $ii + 1
      echo " ftype$jj="'"'$ftype[$ii]'"'                      >> $NAMELIST
    end
    echo '                                    '               >> $NAMELIST
    set ii = 0
    set fnum = $#fname
    while( $ii <  $fnum )
      set jj = $ii
      @ ii = $ii + 1
      if( $fname[$ii] == "none" ) then
        echo " fdate$jj="'"-1"'                               >> $NAMELIST
      else
	if ( $jj == 5 ) then
	  echo " fdate$jj="'"'2016010100000'"'                       >> $NAMELIST
	else
          echo " fdate$jj="'"'$datestr'"'                       >> $NAMELIST
      endif
    end
    echo "/"                                                  >> $NAMELIST

    # Execute NCL program to process the data
    #----------------------------------------
    cat $NAMELIST                     >& $LOGFILE.cfg
    ncl makeIC.ncl NameNumber=$RUNNUM >& $LOGFILE

    #Check to see if the log file contains the text "SUCCESSFULLY COMPLETED PROCESSING"
    #If so, then makeIC_se_002.ncl completed successfully, otherwise it did not.
    #if not then exit False
    #echo "Checking for successfull completion"
    grep -q "SUCCESSFULLY COMPLETED PROCESSING" $LOGFILE
    if( $? == 0 ) then
      : # do nothing and let the program continue
    else
      echo "RNUM ""$RUNNUM"" did not complete successfully, exiting Gen_GEOS5_NEWGRID.csh"
      echo "See "$LOGFILE
      exit 1
    endif

  # End Loop over the hourly values (4X daily)
  #===========================================
  end # foreach hnum ( 1 2 3 4 )

# End loop over time
#=======================
@ NDAYS = $NDAYS + 1
end # while ( $NDAYS < $NUM_DAYS )
