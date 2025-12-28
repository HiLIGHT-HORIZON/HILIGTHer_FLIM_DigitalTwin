% PRE - INIT @RECODE

%%% IMPORTANT: may values get assigned to pixels out of range... verify
%%% why!

%%% WARNING TEMPORAL CALBRATION MOMENTARILY SUPPRESSED!!!!!!!!!!!!!!!!!

if ~exist('bCalibrating')
    bCalibrating = 0 ;
end

if ~bCalibrating
    
    button = questdlg('Please specify type of action','ImFluo - HDIM','Load new file','Load new file (no cal.)','Test calibration','Load new file');

    switch lower(button) 
        case {'load new file'}
            clear all;
            close all
            clc;
            bCal = 1;
            bTest = 0;
            n_bins = 16;
        case {'load new file (no cal.)'}
            clear all;
            close all
            clc;
            bCal = 0;
            bTest = 0;
            n_bins = 16;
        case {'test calibration'}
            bCal = 1;
            bTest = 1;    
            n_bins = 16;
    end
else
            bCal = 0;
            bTest = 1;
            n_bins = 64;
end

bDisplay = 1; % display image while loading
iDisplay = 1; % display mode - 0: last file (only for DEBUGging, img is reset); 1: sum of files; 2: all modules/routing channels

%% FILE NAME HANDLING @RECODE
% DEBUG
%file_name = 'ttt_m*.spc';
%file_path = 'C:\Users\Virgilio Leon Lew\Desktop\SPC\';
%

if bCal
    [file_name file_path] = uigetfile('*.mat','Select the calibration file...');
    eval(['load ''' file_path file_name '''']);
end

if ~bTest
    [file_name file_path] = uigetfile('*.spc','Select one of the SPC files belonging to the dataset of interest...');
    %@@to be recoded>
else
    file_name = file_name3;
    file_path = file_path3;
end

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

% INITIALIZATIONS
%@@@ n_bins should be passed as param, xy tac and rout from spc file
%n_bins  = 16;
x_pxl   = 256;
y_pxl   = 256;
n_rout  = 16; % number of routing channels
tac_res = 2^12; % TAC resolution
delay   = 0;



% initialize
if bTest
    img = zeros([n_mod*n_rout n_bins]);
else
    img = zeros([x_pxl y_pxl n_mod*n_rout n_bins]);
end


% DEBUG (LOAD ONLY TWO FILES ON FIRST MODULE)
     %n_mod = 1; n_fil = 2;
% END DEBUG

%%
for mi = 1:n_mod % SCAN MODULES
    hF = waitbar(0,'File',  'units','normalized','position',[.365 .729 .285 .1]);    
    
    if (bCal & (mi==1))
       delay = HDIM_CAL.Time;
    else
       delay = 0;
    end
    
    for fi = 1:n_fil(mi) % SCAN FILES
        hD = waitbar(0,'Data',  'units','normalized','position',[.365 .599 .285 .1]);     
        
        file_name = [files(1).name(1:is(1)-1) num2str(mi) files(1).name(ie(1)+1:is(2)-1) num2digit(fi,ie(2)-is(2)+1) '.spc'];
        fid = fopen([file_path file_name]); 

        display(['Loading ' file_name '...'])
        
        %read the first byte to skip the header info
        A = fread(fid, [4,1], '*uint8');
        %read entire data to get the total number of photon (4 bytes)
        A = fread(fid, '*uint32');

        %pre-allocate the memory
        N  = length(A)-1; % remove 32 bits of the fifo image header
        mt = zeros(N,1);
        rt = zeros(N,1);
        mk = zeros(N,1);
        gp = zeros(N,1);
        mt = zeros(N,1);
        in = zeros(N,1);        
        ut = zeros(N,1);
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

        %begin block processing
        % DEBUG
%          rp = 1;
%          N  = 250000;

        % read the first 4 bytes of the fifo image header
        data   = fread(fid, 4, '*uint8')';  
        mt_clk = double(data(1:3))*[1; 2^4; 2^8]*.1; % (ns) microtime clock in nanoseconds is computed from the first 3 bytes of a fifo image and t is expressed in 0.1 ns units
        rt_bit = double(bitget(data(4),(4:7)))*2.^(0:3)'; % number of routing bits is computed by selecting the 4th to 7th bit in the last byte. First bytes are reserved
        %dt_inv = double(bitget(data(4),8))
        
        %%% @@@@ MUST INCLUDE PARSING OF SET FILE
        px_clk = 2.9e-06;
        
        while (rp<N); %SCAN DATA BLOCK
            data = fread(fid, [2, block_size], '*uint16')';
            [mt_ rt_ ut_ mk_ gp_ mv_ in_  seg_checker remainder of_] = if_bh_parse_fifoimagestream(data, block_size);
              
            rpn = rp+block_size-remainder-1;
            
            mt(rp:rpn, 1) = mt_;
            rt(rp:rpn, 1) = rt_;
            mk(rp:rpn, 1) = mk_;
            gp(rp:rpn, 1) = gp_;
            mv(rp:rpn, 1) = mv_;
            in(rp:rpn, 1) = in_;                    
            ut(rp:rpn, 1) = ut_;            
            of(rp:rpn, 1) = of_;
            
            checker(rp:rpn, 1)   = seg_checker;
            
            %%% Update row pointer
            rp = rp + block_size;
            
            waitbar(rp/N,hD)
        end %END SCAN DATABLOCK
            
        
        % IMPORTANT TO BE REINSTERTED/RECODED
        overflow_cumulative = cumsum(of);
        %clear of;
        mt = mt + (overflow_cumulative * 4096);        
       %find invalid photons    
        %seta = [49152 32768];    %49152 MTOV and INV are 1; 32768 is just invalid
        %n = find(ismember(checker, seta));
        % next line can replace previous one
        n = find((in==1)|(in==1&mv==1));
        
        %mt(n) = [];
        %ut(n) = [];
%         
%          idx = find(in==1&mk~=1);
%          mt(idx)=[];
%          ut(idx)=[];
%          rt(idx)=[];
%          mk(idx)=[];
%          in(idx)=[];
        
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
        np = length(ut);
                
        
        
        %number of macrotime per pixel px_clk/(12.5*1e-9)
        % ((1/400)/256)/(12.5*1e-9) the same from SP5... it seems the correct one
        % mean(diff(mt(find(mk==1&rt==6))))/(256*256) average mt per pixelframe
        % mean(diff(mt(find(mk==1&rt==2))))/256 considering line
        
        mtperpixel = 800;% mean(diff(mt(find(mk==1&rt==2))))/255;
        
        
        % scan individual entries to identify photons and trigger signals                
        frame_count = 1;
        tmp=[];
        
        for ip=1:np            
           if mk(ip)==1
               if rt(ip)==1 % pixel                   
                    x = x + 1;
               elseif rt(ip)==2 %line
                    y = y + 1;
                    x = 1;
               elseif rt(ip)==6 %frame
                    x = 1;
                    y = 1;
                    
                    frame_count = frame_count + 1;
               end
               % DEBUG
               if x>x_pxl | y>y_pxl                    
                    chkx(ip) = x;               
                    chky(ip) = y;                    
               end    
               
               %
           else
               
               if 1 % define x position when no clock pixel marker is provided
                   x = round((mt(ip)/mtperpixel)/(256*frame_count))+1;
                   tmp(ip)=x';
               end
                if ~in(ip)& ~(x>x_pxl | y>y_pxl)   
                    t = ceil((ut(ip)+1)/((tac_res+delay)/n_bins)); % identify time bin
                    if bTest
                        img((mi-1)*16+rt(ip)+1,t) = img((mi-1)*16+rt(ip)+1,t) + 1;                      
                    else
                        img(x,y,(mi-1)*16+rt(ip)+1,t) = img(x,y,(mi-1)*16+rt(ip)+1,t) + 1;                      
                    end
                end            
           end
             %ip/np
        end
                
%% DISPLAY - MAIN
        if bDisplay&~bTest
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
%         figure,plot(cumsum(rt(find(mk==1))==1))
%         hold on
%         line=cumsum(rt(find(mk==1))==2);
%         frame=cumsum(rt(find(mk==1))==6);
%         plot((line)*256,'r')
%         plot(frame*256*256,'k')
    fclose(fid)
    waitbar(fi/n_fil(mi), hF)
    end    % END SCAN FILES
    close(hF)
    waitbar(mi/n_mod, hM)
end % END SCAN MODULES

%%
close(hM)
if ~bTest
    figure,plot(reshape(squeeze(sum(sum(sum(img,1),2),4))',[16 2]))
    tmp = squeeze(sum(sum(img,1),2))';
    figure,plot(tmp);
end
eval(['save ' file_name(1:end-11)])