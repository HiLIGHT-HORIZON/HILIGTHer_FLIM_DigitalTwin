function [blk, img] = if_bh_parsedatablock(fid,dbl_off,msd)
blk = struct();

% parsing block type, these should be types constants and global
BLK_TYP_CRE = {'not used', 'measured', 'flow', 'measured from file', 'calculated', 'simulated', 'fifo', 'fifo from file', 'moments', 'moments from file'};
BLK_TYP_CON = {'decay', 'page (set of decay curves)', 'fcs', 'fida', 'filda', 'mcs', 'fifo image (PS)', 'mcsta', 'fifo image (MCS)', 'moments'};
BLK_TYP_TYP = {'ushort', 'ulong', 'double'};
BLK_TYP_ZIP = {'not zipped', 'zipped'};


% read data block header
fseek(fid,dbl_off,'bof');

blk.num = fread(fid, 1,'short'); % obsolete
blk.off = fread(fid, 1,'long');
blk.nxt = fread(fid, 1,'long'); % offset of the next datablock
blk.typ = dec2bin(fread(fid, 1,'ushort'),16);
blk.msr = fread(fid, 1,'short'); % number of the measurement description block corresponding to this data block
blk.lbn = dec2bin(fread(fid, 1,'ulong'),32); % instead of blk_num, provide more information on the block, parsed later
blk.len = fread(fid, 1,'ulong');

blk.typ_cre = bin2dec(blk.typ(end-3:end))+1; % creation mode
blk.typ_con = (bin2dec(blk.typ(end-7:end-4)))+1; % block content@@@ CHECK IF OK, original spec in HEX
blk.typ_typ = (bin2dec(blk.typ(end-11:end-8)))+1; % variable type @@@ CHECK original spec in HEX
blk.typ_zip = (bin2dec(blk.typ(end-12:end-12)))+1; % zipped?
%(bin2dec(blk_typ(end-15:end-13))) bits not used

display(['Block type:' BLK_TYP_CRE{blk.typ_cre} ', ', ...
                       BLK_TYP_CON{blk.typ_con} ', ', ...
                       BLK_TYP_TYP{blk.typ_typ} ', ', ...
                       BLK_TYP_ZIP{blk.typ_zip} ', ', ...
                      ]);
% read data block
fseek(fid,blk.off,'bof');
switch blk.typ_con % change to constant defitiions @@@
    case 1,2 % FLIM, imaging % 1 added only for debuggin
        img = fread(fid, msd.adc_re*msd.scan_x*msd.scan_y,'ushort');        
        img = reshape(img,[msd.adc_re msd.scan_x msd.scan_y]);
        img = shiftdim(img,1);  
        
        %%%% PARSING BLOCK for blk_lbn 
        
    case 7 % FIFO image - add another switch @@@ for FCS etc... now only
        % Parsing Block Long Numbering blk_lbn
        %bin2dec(blk_lbn(end-23:end-20)) equal to blk_typ_con-1
        routing_channel = bin2dec(blk.lbn(end-7:end));
        
        img = fread(fid, msd.adc_re*msd.image_x*msd.image_y,'ushort');        
        img = reshape(img,[msd.adc_re msd.image_x msd.image_y]);
        img = shiftdim(img,1);
        
        display(['routing channel: ' num2str(routing_channel)])
    otherwise
        
      display('if_bh_loadsdt> data format not supported')
      
end