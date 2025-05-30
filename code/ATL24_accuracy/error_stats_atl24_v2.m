%% error_stats_atl24_v2.m
% Computes vertical error statistics (RMSE, Accuracyz, skewness, kurtosis,
% etc.) from an input file of DeltaZ's for an ATL24 accuracy test. Each 
% deltaZ is computed as: Z_ATL24 - Z_reference. The procedures are designed 
% to follow, to the extent applicable, the ASPRS Positional Accuracy 
% Standards for Digital Geospatial Data, although the script performs some 
% additional computations that are not in the current ASPRS standards. The 
% original version of this error_stats script was written on 4/16/2021, 
% before the release of the 2nd Edition of the ASPRS standards, and some 
% of the computed metrics, which were in the previous version of the 
% standards are not in the current version (e.g., the 95% confidence level 
% and 95th percentile absolute error).
% 
% C. Parrish (christopher.parrish@oregonstate.edu)
% 2/26/2025
% This is based on my original error_stats.m script, which was written on 
% 4/16/2021 and updated on 4/29/2021 to: 1) include normality test, and 
% 2) to make the number of bins in the error histogram a user-selectable 
% parameter; and 3) to compute the 95th percentile absolute error. It was 
% again updated on 12/30/2022 to use Lilliefors test for normality, rather 
% than the K-S test. Note that the Lilliefors test is based on the K-S 
% test, but includes improvements to the K-S test and does not require 
% that the expected value and variance of the distribution be known. This
% version was written on 2/26/2025 for ATL24 accuracy testing. It was 
% updated again on 3/9/2025 to add option to remove outliers. However, a 
% caveat: according to the ASPRS Positional Accuracy Standards for Digital 
% Geospatial Data, 2nd Ed,it is improper and in violation of the standards 
% to remove outliers, without inspection, simply because their errors are 
% more than some number of standard deviations from the mean.
%%
clear all; close all; clc;

%% User-entered parameters
rootDir = strcat('G:\01Chris\ATL24\');
csvFname = 'Sandy_Neck_Just_DeltaZs_High_Confidence.csv';
siteName = 'Sandy Neck - Just High Confidence';
projectUnits = 'm';       % Specify the project units as ft or m
                           % Note: this should match the units of the 
                           % elevation residuals (vertical errors) in the
                           % DeltaZfile
numBins = 30;               % Number of bins in error histogram (integer)
removeOutliers = false;     % Set to true if you want to remove outliers
outlierThresh = 2.5;        % Number of standard deviations from the mean
                           % in which to remove outliers

%% Create the DeltaZ full path and filename by concatinating the path and 
% csv file name
deltaZfile = [rootDir,csvFname];

%% Displate the site name to the screen
disp(['Accuracy Stats for ' siteName]);
disp('-------------------------------------------');

%% Read in the DeltaZ file
deltaZs = readmatrix(deltaZfile,'NumHeaderLines',1);

%% Remove outliers, if the flag is set. Please see note of caution 
% regarding ASPRS wording on removing outliers without inspection.
numOutliersRemoved = 0;
if removeOutliers
    numPtsBefore = length(deltaZs);
    deltaZsMean = mean(deltaZs);
    deltaZsStDev = std(deltaZs);
    % Identify the indices of outliers
    outlierIndices = abs(deltaZs - deltaZsMean) > outlierThresh*deltaZsStDev;
    % Remove the outliers
    deltaZs = deltaZs(~outlierIndices);
    numPtsAfter = length(deltaZs);
    numOutliersRemoved = numPtsBefore - numPtsAfter;
end

%% Compute RMSE and accuracy at 95% confidence level
diffSq = deltaZs.^2;  % Differences squared
rmse = sqrt(mean(diffSq));
accuracyz = 1.9600*rmse;

%% Compute standard deviation and other stats
numCheckpts = length(deltaZs);
stdevDz = std(deltaZs);
biasDz = mean(deltaZs);
minDz = min(deltaZs);
maxDz = max(deltaZs);
skewDz = skewness(deltaZs);
kurtDz = kurtosis(deltaZs);

%% Compute the accuracy at the 95% confidence level with the bias removed
deltaZsNoBias = deltaZs - biasDz;
diffSqNoBias = deltaZsNoBias.^2;
rmseNoBias = sqrt(mean(diffSqNoBias));
accuracyzNoBias = 1.9600*rmseNoBias;

%% Compute the Median Absolute Error (MedAE)
MedAE = median(abs(deltaZs));

%% Perform Lilliefors test for normality
h = lillietest(deltaZs);
if h == 0
    disp('DeltaZs conform to normal distribution based on normality test')
elseif h == 1
    disp('DeltaZs do not conform to normal distribution based on normality test')
else
    disp('Warning: check format of input data')
end

%% Compute the 95th percentile absolute error 
Q95 = prctile(abs(deltaZs),95);  % Note: this works, but it gives a very
                                   % slightly different answer than the
                                   % ASPRS method of computing Q95
% Q95_ASPRS = percentile_error(deltaZs);

%% Display the results to the screen
disp(['Number of outliers removed: ' num2str(numOutliersRemoved)]);
disp(['N = ' num2str(numCheckpts)]);
disp(['RMSE = ' num2str(rmse) ' ' projectUnits]);
disp(['ASPRS Vertical Accuracy Class = ' num2str(rmse) ' ' projectUnits]);
disp(['Accuracyz at 95% CL = ' num2str(accuracyz) ' ' projectUnits]);
disp(['Accuracyz at 95% CL with bias removed = ' ...
    num2str(accuracyzNoBias) ' ' projectUnits]);
disp(['Standard deviation = ' num2str(stdevDz) ' ' projectUnits]);
disp(['Mean = ' num2str(biasDz) ' ' projectUnits]);
disp(['Min = ' num2str(minDz) ' ' projectUnits]);
disp(['Max = ' num2str(maxDz) ' ' projectUnits]);
disp(['Skewness = ' num2str(skewDz)]);
disp(['Kurtosis = ' num2str(kurtDz)]);
% disp(['95th percentile absolute error = ' num2str(Q95_ASPRS) ' ' ...
%     projectUnits]);
disp(['Median Absolute Error: ', num2str(MedAE) ' ' projectUnits]);

%% Plot error histogram with a fitted Gaussian
figure
histfit(deltaZs,numBins);
xlabel(['\DeltaZ (' projectUnits ')'],'FontSize',15);
ylabel('Number of Occurrences','FontSize',14);
title('Error Histogram','FontSize',16);
% Plot the mean
xline(biasDz,'r-','Mean','FontSize',14,'LineWidth', 2);
set(gcf,'Color','white');
% xlim([-2 2])
ax = gca; 
ax.FontSize = 13; 

%% Compute quartiles
cleanErrors = deltaZs(~isnan(deltaZs));
quartiles = quantile(cleanErrors, [0.25 0.5 0.75]);
Q1 = quartiles(1);
Q2 = quartiles(2);  % median
Q3 = quartiles(3);
disp(['Q1 (25th percentile): ' num2str(Q1) ' ' projectUnits]);
disp(['Q2 (median): ' num2str(Q2) ' ' projectUnits]);
disp(['Q3 (75th percentile): ' num2str(Q3) ' ' projectUnits]);