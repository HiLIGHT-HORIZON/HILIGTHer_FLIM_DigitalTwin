% img = if_bh_loadsdt;                              load SDT file calling GUI for location of the files
% img = if_bh_loadsdt(file_name);                   load SDT file specified by file_name
% [img, hdr, asc, stp, msd] = if_bh_loadsdt(...);   load SDT files and information on the measurements
%
% WARNING: currently only the first MSD block is loaded... must include handling of multiple MSD blocks

function varargout = if_bh_loadsdt(varargin)

    if nargin==0
        [file_name file_path] = uigetfile('*.sdt','Select a SDT B&H file...');
        file_name = [file_path file_name];
    elseif nargin==1        
         file_name = varargin{1};
    else
        display([mfilename '> wrong number of arguments, trying to execute...'])         
    end
    
    fid = fopen(file_name); 
    
    %% 
    hdr        = if_bh_parseheader(fid);                        % read header
    asc        = if_bh_parseinfo(fid,hdr.inf_off);              % read info ascii
    stp        = if_bh_parsesetup(fid,hdr.set_off);             % read setup

    %%% WARNING @@@ I CANNOT TRACE THE LOCATION OF ALL MSDs BUT ONLY THE FIRST... need checking
    msd        = if_bh_parsemsd(fid,hdr.msd_off);               % read measurement block

    ae.x = max([msd.scan_x msd.image_x]);
    ae.y = max([msd.scan_y msd.image_y]);
    img  = zeros([ae.x ae.y hdr.dbl_num msd.adc_re]);
    
    rtn = [];
    
    next_block = hdr.dbl_off;
    for dbi=1:hdr.dbl_num % scan all data blocks    
        [blk, tmp] = if_bh_parsedatablock(fid,next_block,msd);     % read datablock
        next_block = blk.nxt;
        img(:,:,dbi,:) = reshape(tmp,[size(tmp,1) size(tmp,2) 1 size(tmp,3)]);
        
        rtn(dbi)= bin2dec(blk.lbn(end-7:end));
    end


    % For Debugging
    %figure,imshow(rgbfill(sumch(img,[4])))
    %figure
    %imagesc(medfilt2(squeeze(sum(sum(img,3),4)),[2 2]))
    %colormap(flipud(gray))
    %colorbar
    %axis image
    %axis off
    %figure,plot(squeeze(sum(sum(img,1),2)))
    %rgb = if_hdim_spec2rgb(sumch(img,4),'type','perception');
    %imshow(imadjust(rgb,[0 .1],[0 1]));        


    %%
    fclose(fid);
    
    if nargout==1
        varargout{1} = img;
    elseif nargout==2
        varargout(1:2) = {img,rtn};
    elseif nargout==5
        varargout(1:5) = {img, hdr, asc, stp, msd};
    else
        display([mfilename '> wrong number of output arguments, trying to execute,...'])
        tmpout = {img, hdr, asc, stp, msd};        
        for ai=1:nargout
            if ai>5
                varargout{ai} = '';
            else
                varargout{ai} = tmpout{ai};
            end
        end
    end