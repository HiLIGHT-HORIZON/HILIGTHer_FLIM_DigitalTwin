% Parse file name for SPC loading
% Scan all files specified by file_path and file_name to identify the
% position of module and file numbers
%
% file_name should contain wildcard "*"
%
% returns:
% nc (integer) - number of clusters, typically used with nc=2, module and
%                file number
% is (integer array) - start position of changing cluster
% ie (integer array) - end position of changing cluster
% fn (integer) - total number of files
% files (cell of strings) - file names

function [nc, is, ie, fn, files] = if_bh_parsefilename(file_path, file_name)
    % check if file_path ends with a slash
    if ~sum(strcmp(file_path(end),{'\','/'}))
        file_path = [file_path '\'];
    end
    
    files      = dir([file_path file_name]);
    files_mask = [];

    % Scan and compare all file names to find clusters of changing numbers    
    fn = length(files);
    for fi=2:fn
        tmp = files(1).name==files(fi).name;    
        if length(files_mask)==0
            files_mask = tmp;
        else
            files_mask = files_mask + tmp;
        end
    end
    % mark only changing characters
    files_mask = files_mask~=files_mask(1);
    % Add an extra charater at start to avoid missing a changing character at position 1
    files_mask = diff([0 files_mask]);

    nc = sum(files_mask==1); % number of clusters
    is = find(files_mask==1); % start of clusters
    ie = find(files_mask==-1)-1; % end of clusters