% PRE - INIT @RECODE

%%% IMPORTANT: may values get assigned to pixels out of range... verify
%%% why!

clear all;
close all
clc;

bDisplay = 1; % display image while loading
iDisplay = 1; % display mode - 0: last file (only for DEBUGging, img is reset); 1: sum of files; 2: all modules/routing channels

%% FILE NAME HANDLING @RECODE
% DEBUG
%file_name = 'ttt_m*.spc';
%file_path = 'C:\Users\Virgilio Leon Lew\Desktop\SPC\';
%
[file_name file_path] = uigetfile('*.spc','Select one of the SPC files belonging to the dataset of interest...');
% @to be recoded>
file_name = [file_name(1:end-9) '*.spc'];
[nc is ie fn files] = if_bh_parsefilename(file_path, file_name);

%% parse numbering
n_mod = []; % number of modules (1 or 2 currently supported)
n_fil = []; % number of files/module
% compute number of modules
if nc==2
    for fi = 1:fn
        n_mod(fi) = str2num(files(fi).name(is(1):ie(1)));
    end
else
    n_mod = 1;
end
n_mod = max(n_mod);

% number of files per module
n_fil(1:n_mod) = 1;
for fi = 1:fn
    tmp = str2num(files(fi).name(is(nc):ie(nc)));
    if n_mod>1
        mi = str2num(files(fi).name(is(1):ie(1)));
    else
        mi = 1;
    end
    n_fil(mi) = max([n_fil(mi) tmp]);
end

clear fi files_mask tmp nc ic fn mi

%% Initialize graphics
hM = waitbar(0,'Module','units','normalized','position',[.365 .859 .285 .1]);
hI = figure('units','normalized','position',[.01 .5 .35 .4]);

% user defined
n_bins  = 16; % number of time bins
% defined by "set": add parsing 
n_rout  = 16; % number of routing channels
tac_res = 2^12; % TAC resolution
x_pxl   = 256;
y_pxl   = 256;

% initialize
img     = zeros([x_pxl y_pxl n_mod*n_rout n_bins]);


% DEBUG (LOAD ONLY TWO FILES ON FIRST MODULE)
     %n_mod = 1; n_fil = 2;
% END DEBUG

%%
for mi = 1:n_mod % SCAN MODULES
    hF = waitbar(0,'File',  'units','normalized','position',[.365 .729 .285 .1]);    
    
    for fi = 1:n_fil(mi) % SCAN FILES
        hD = waitbar(0,'Data',  'units','normalized','position',[.365 .599 .285 .1]);     
        
        file_name = [files(1).name(1:is(1)-1) num2str(mi) files(1).name(ie(1)+1:is(2)-1) num2digit(fi,ie(2)-is(2)+1) '.spc'];
        fid = fopen([file_path file_name]); 

        %read the first byte to skip the header info
        A = fread(fid, [4,1], '*uint8');
        %read entire data to get the total number of photon (4 bytes)
        A = fread(fid, '*uint32');

        %pre-allocate the memory
        N = length(A);
        macrotime = zeros(N,1);
        routing   = zeros(N,1);
        mark      = zeros(N,1);
        gap       = zeros(N,1);
        mtov      = zeros(N,1);
        invalid   = zeros(N,1);        
        utime     = zeros(N,1);
        checker   = zeros(N,1);
        overflow  = zeros(N,1);
        % DEBUG
        chkx  = zeros(N,1);
        chky  = zeros(N,1);
        %
        clear A;

        %%restart the fread function
        frewind(fid); 

        block_size = 50000;
        rp = 1;
   
        %read header info
        A = fread(fid, [4,1], '*uint8');   
        clear('A','h1');

        %begin block processing
        % DEBUG
%          rp = 1;
%          N  = 250000;
%         
        while (rp<N); %SCAN DATA BLOCK
            seg_A = fread(fid, [2, block_size], '*uint16');
            [seg_macrotime seg_routing seg_mark seg_gap seg_mtov seg_invalid seg_utime seg_checker remainder seg_overflow] = seg_data_extraction1(seg_A);
              
            macrotime(rp:rp+block_size-remainder-1, 1) = seg_macrotime;
            routing(rp:rp+block_size-remainder-1, 1)   = seg_routing;
            mark(rp:rp+block_size-remainder-1, 1)      = seg_mark;
            gap(rp:rp+block_size-remainder-1, 1)       = seg_gap;
            mtov(rp:rp+block_size-remainder-1, 1)      = seg_mtov;
            invalid(rp:rp+block_size-remainder-1, 1)   = seg_invalid;                    
            utime(rp:rp+block_size-remainder-1, 1)     = seg_utime;
            checker(rp:rp+block_size-remainder-1, 1)   = seg_checker;
            overflow(rp:rp+block_size-remainder-1, 1)  = seg_overflow;
            %%% Update row pointer
            rp = rp + block_size;
            
            waitbar(rp/N,hD)
        end %END SCAN DATABLOCK
            
        
        % IMPORTANT TO BE REINSTERTED/RECODED
        %overflow_cumulative = cumsum(overflow);
        %clear overflow;
        %macrotime = macrotime + (overflow_cumulative * 4096);        
       %find invalid photons    
        %seta = [49152 32768];         
        %n = find(ismember(checker, seta));
        %macrotime(n) = [];
        %utime(n) = [];
%         
%          idx = find(invalid==1&mark~=1);
%          macrotime(idx)=[];
%          utime(idx)=[];
%          routing(idx)=[];
%          mark(idx)=[];
%          invalid(idx)=[];
        
        close(hD)
        
%% BUILD IMAGE        
        % init
        if bDisplay & iDisplay==0  
            img(:,:,:,:) = 0;
        end
    
        
        if fi==1 % reset pixel position at the start of new module
            x  = 1;
            y  = 1;            
        end
        in = length(utime);
                
        % scan individual entries to identify photons and trigger signals                
        for ip=1:in            
           if mark(ip)==1
               if routing(ip)==1 % pixel                   
                    x = x + 1;
               elseif routing(ip)==2 %line
                    y = y + 1;
                    x = 1;
               elseif routing(ip)==6 %frame
                    x = 1;
                    y = 1;
               end
               % DEBUG
               if x>x_pxl | y>y_pxl                    
                    chkx(ip) = x;               
                    chky(ip) = y;                    
               end    
               
               %
           else
                if ~invalid(ip)& ~(x>x_pxl | y>y_pxl)   
                    t = ceil((utime(ip)+1)/(tac_res/n_bins)); % identify time bin
                    img(x,y,(mi-1)*16+routing(ip)+1,t) = img(x,y,(mi-1)*16+routing(ip)+1,t) + 1;                      
                end            
           end
             %ip/in
        end
                
%% DISPLAY - MAIN
        if bDisplay
            figure(hI);
            switch iDisplay
                case {0,1}
                    imagesc(squeeze(sum(sum(img,3),4)))
                    set(gca,'clim',[0 250]);                    
                case 2 % display all data                    
                    for aa=1:32
                        subplot(4,8,aa); 
                        imagesc(squeeze(sum(img(:,:,aa,:),4)));
                        set(gca,'clim',[0 300]);
                        axis image
                        axis off
                    end
            end                        
            drawnow
        end

        %clear('N','block_size','checker','fid', 'n','set','remainder', 'rp', 'filename','full_filename');
        clear('-regexp', '|^over|^seg|');


        %% DEBUG
%         figure,plot(cumsum(routing(find(mark==1))==1))
%         hold on
%         line=cumsum(routing(find(mark==1))==2);
%         frame=cumsum(routing(find(mark==1))==6);
%         plot((line)*256,'r')
%         plot(frame*256*256,'k')

    waitbar(fi/n_fil(mi), hF)
    end    % END SCAN FILES
    close(hF)
    waitbar(mi/n_mod, hM)
end % END SCAN MODULES

%%
close(hM)
figure,plot(reshape(squeeze(sum(sum(sum(img,1),2),4))',[16 2]))
tmp = squeeze(sum(sum(img,1),2))';
figure,plot(tmp);