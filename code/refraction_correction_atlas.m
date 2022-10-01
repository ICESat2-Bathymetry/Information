function [E_new, N_new, Z_new]=refraction_correction_atlas_UPDATE(E, N, Z, W, ...
    ref_elev, ref_azimuth, deltaTheta, n1, n2)

% This function is desinged to apply a first-order refraction correction to 
% geolocated ICESat-2 ATLAS seafloor returns. By applying this function,
% the refraction and change in speed of light at the air-water interface 
% are accounted for.
% Input:
%  E = easting of uncorrected lidar point
%  N = northing of uncorrected lidar point
%  Z = height (generally, orthometric height, H) of uncorrected lidar point 
%  W = height of water surface from water surface model at location (E, N)
%      Note: depending on the application, it may be acceptable to just
%      assume a constant water surface elevation, W.
%  ref_elev = the variable ref_elev, as defined in the ATL03 documentation:
%             Elevation of the unit pointing vector for the reference 
%             photon in the local ENU frame in radians. The angle is 
%             measured from east-north plane and positive towards up.
%  ref_azimuth = the variable ref_azimuth, as defined int the ATL03
%                documentation: Azimuth of the unit pointing vector for the 
%                reference photon in the local ENU frame in radians. The 
%                angle is measured from north and positive towards east.
%  deltaTheta = empirically-determined angular misalignment correction
%  n1 = refractive index of air (default value = 1.00029)
%  n2 = refractive index of water (default value = 1.34116)
% Output:
%  E_new = corrected easting of lidar point
%  N_new = corrected northing of lidar point
%  Z_new = corrected height of lidar point
%
% C. Parrish (christopher.parrish@oregonstate.edu
% Written: 12/21/2018, 
% Modified: 3/1/2019: The original version was designed to be tested on 
% airborne bathymetric lidar (and was tested on Riegl VQ-880-G data for 
% Lake Tahoe). This version is specifically for ATLAS.
% Modified: 3/20/2019: Added Earth curvature correction and also an
% empirically-determined angular misalignment correction. Based on
% correspondence with Lori Magruder, this correction is ~5 deg.

%% Input arguments
if nargin==7
    n1 = 1.00029;       % Default refractive index of air
    n2 = 1.34116;       % Default refractive index of seawater 
end

%% Preprocessing step: compute the Earth curvature correction. This 
% correction uses a mean radius of the Earth of 6371 km and a mean orbital
% altitude of ICESat-2 of 496 km
thetaEC = atan(496*tan(deg2rad(ref_elev))/6371);

%% Step 0: convert ref_elev, which is defined in ATL03 as the elevation of
% the unit pointing vector in the local ENU frame in radiance measured from 
% the E-N plane positive towards up to incidence angle, theta1.
theta1 = pi/2 - abs(ref_elev) + thetaEC - deltaTheta;

%% Step 1: Compute D = Wij – Zij, where D is the uncorrected depth
D = W - Z;

%% Step 2: 	Compute theta2 from Eq. 2, where theta2 is the angle of 
% refraction
theta2 = asin(n1*sin(theta1)/n2);

%% Step 3: Compute S from Eq. 4, where S is the uncorrected slant range to 
% the uncorrected bottom return photon location
S = D/cos(theta1);

%% Step 4: Compute R from Eq. 3, where R is the corrected slant range
R = (S*n1)/n2;

%% Step 5: Compute P from Eq. 10, where P is the distance between the 
% uncorrected and corrected photon return points in the Y-Z plane
P = sqrt(R^2+S^2-2*R*S*cos(theta1-theta2)); 

%% Step 6: Compute beta from Eq. 11
beta = (pi/2) - theta1 - asin(R*sin(theta1-theta2)/P);

%% Step 7: Compute DeltaY and DeltaZ from Eq. 12-13, where DeltaY and 
% DeltaZ are the offsets in the cross-track and vertical directions, 
% respectively
DeltaY = P*cos(beta);
DeltaZ = P*sin(beta);

%% Step 8: Compute the cross track offset in the mapping frame
DeltaE = DeltaY*sin(ref_azimuth);
DeltaN = DeltaY*cos(ref_azimuth);

%% Step 9: add the corrections to the original coordinates
E_new = E + DeltaE;
N_new = N + DeltaN;
Z_new = Z + DeltaZ;
     





