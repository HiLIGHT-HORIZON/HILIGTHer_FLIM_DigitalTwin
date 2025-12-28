function hdr = if_bh_parseheader(fid)

hdr = struct();

%READ HEADER
hdr.rev     = fread(fid, 1,'short');   % revision, cannot parse properly
hdr.inf_off = fread(fid, 1,'long');    % information block, offset
hdr.inf_len = fread(fid, 1,'short');   % information block, length
hdr.set_off = fread(fid, 1,'long');    % setup block, offset
hdr.set_len = fread(fid, 1,'short');   % setup block, length
hdr.dbl_off = fread(fid, 1,'long');    % data block, offset
hdr.dbl_num = fread(fid, 1,'short');   % data block, number of
hdr.dbl_len = fread(fid, 1,'long');    % data block, length
hdr.msd_off = fread(fid, 1,'long');    % measurement description data block, offset
hdr.msd_num = fread(fid, 1,'short');   % measurement description data block, number of
hdr.msd_len = fread(fid, 1,'short');   % measurement description data block, length

hdr.bHvalid   = (fread(fid, 1,'ushort')==21845);
hdr.reserved1 = fread(fid, 1,'ulong');
hdr.reserved2 = fread(fid, 1,'ushort');
hdr.chksum    = fread(fid, 1,'ushort');