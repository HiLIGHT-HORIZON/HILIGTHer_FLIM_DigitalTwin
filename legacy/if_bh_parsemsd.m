function msd = if_bh_parsemsd(fid,msd_off)

%% READ MEASUREMENT DESCRIPTION DATA BLOCK
msd = struct();

fseek(fid,msd_off,'bof');

msd.time = fread(fid, 9,'*char')';
msd.date = fread(fid, 11,'*char')';
msd.serial_number = fread(fid, 16,'*char')';
msd.meas_mode = fread(fid, 1,'short');
% CFD
msd.cfd_ll = fread(fid, 1,'float');
msd.cfd_lh = fread(fid, 1,'float');
msd.cfd_zc = fread(fid, 1,'float');
msd.cfd_hf = fread(fid, 1,'float');
% SYNC
msd.syn_zc = fread(fid, 1,'float');
msd.syn_fd = fread(fid, 1,'short');
msd.syn_hf = fread(fid, 1,'float');
% TAC
msd.tac_r  = fread(fid, 1,'float');
msd.tac_g  = fread(fid, 1,'short');
msd.tac_of = fread(fid, 1,'float');
msd.tac_ll = fread(fid, 1,'float');
msd.tac_lh = fread(fid, 1,'float');
%
msd.adc_re  = fread(fid, 1,'short');
msd.eal_de  = fread(fid, 1,'short');
msd.ncx     = fread(fid, 1,'short');
msd.ncy     = fread(fid, 1,'short');
msd.page    = fread(fid, 1,'ushort');
%
msd.col_t     = fread(fid, 1,'float');
msd.rep_t     = fread(fid, 1,'float');
msd.stopt     = fread(fid, 1,'short');
msd.overfl    = fread(fid, 1,'*char')';
msd.use_motor = fread(fid, 1,'short');
msd.steps     = fread(fid, 1,'ushort');
%
msd.offset   = fread(fid, 1,'float');
msd.diether  = fread(fid, 1,'short');
msd.incr     = fread(fid, 1,'short');
msd.mem_bank = fread(fid, 1,'short');
msd.mod_type = fread(fid, 16,'*char')';
msd.syn_th  = fread(fid, 1,'float');
%
msd.dead_time_comp = fread(fid, 1,'short');
msd.polarity_l     = fread(fid, 1,'short');
msd.polarity_f     = fread(fid, 1,'short');
msd.polarity_p     = fread(fid, 1,'short');
msd.linediv        = fread(fid, 1,'short');
% pixel
msd.accumulate = fread(fid, 1,'short');
msd.flbck_y    = fread(fid, 1,'int32');
msd.flbck_x    = fread(fid, 1,'int32');
msd.bord_u     = fread(fid, 1,'int32');
msd.bord_l     = fread(fid, 1,'int32');
msd.pix_time   = fread(fid, 1,'float');
msd.pix_clk    = fread(fid, 1,'short');
msd.trigger    = fread(fid, 1,'short');
msd.scan_x     = fread(fid, 1,'int32');
msd.scan_y     = fread(fid, 1,'int32');
msd.scan_rx    = fread(fid, 1,'int32');
msd.scan_ry    = fread(fid, 1,'int32');
%
msd.fifo_type     = fread(fid, 1,'short');
msd.epx_div       = fread(fid, 1,'int32');
msd.mod_type_code = fread(fid, 1,'ushort');
msd.mod_fpga_ver  = fread(fid, 1,'ushort');

msd.overflow_corr = fread(fid, 1,'float');
msd.adc_zoom      = fread(fid, 1,'int32');
msd.cycles        = fread(fid, 1,'int32');

%MeasStopInfo BLOCK - Information collected when measurement is finished
msd.status        = fread(fid, 1,'ushort');
msd.flags         = fread(fid, 1,'ushort');
msd.stop_time     = fread(fid, 1,'float');
msd.cur_step      = fread(fid, 1,'int32');
msd.cur_cycle     = fread(fid, 1,'int32');
msd.cur_page      = fread(fid, 1,'int32');
msd.min_syn_rate  = fread(fid, 1,'float');
msd.min_cfd_rate  = fread(fid, 1,'float');
msd.min_tac_rate  = fread(fid, 1,'float');
msd.min_adc_rate  = fread(fid, 1,'float');
msd.max_syn_rate  = fread(fid, 1,'float');
msd.max_cfd_rate  = fread(fid, 1,'float');
msd.max_tac_rate  = fread(fid, 1,'float');
msd.max_adc_rate  = fread(fid, 1,'float');
msd.reserved1     = fread(fid, 1,'int32');
msd.reserved2     = fread(fid, 1,'float');

%MeasFCSInfo - Information collected when FIFO measurement is finished
msd.channel        = fread(fid, 1,'ushort');
msd.fcs_decay_calc = fread(fid, 1,'ushort');
msd.mt_resol       = fread(fid, 1,'int32');
msd.cortime        = fread(fid, 1,'float');
msd.calc_photons   = fread(fid, 1,'uint32');
msd.fcs_points     = fread(fid, 1,'int32');
msd.end_time       = fread(fid, 1,'float');
msd.overruns       = fread(fid, 1,'ushort');
msd.fcs_type       = fread(fid, 1,'ushort');
msd.cross_chan     = fread(fid, 1,'ushort');
msd.mod            = fread(fid, 1,'ushort');
msd.cross_mod      = fread(fid, 1,'ushort');
msd.cross_mt_resol = fread(fid, 1,'uint32');
% 
msd.image_x   = fread(fid, 1,'int32');
msd.image_y   = fread(fid, 1,'int32');
msd.image_rx  = fread(fid, 1,'int32');
msd.image_ry  = fread(fid, 1,'int32');
msd.xy_gain   = fread(fid, 1,'short');
msd.dig_flags = fread(fid, 1,'short');
msd.adc_de    = fread(fid, 1,'short');
msd.det_type  = fread(fid, 1,'short');
msd.x_axis    = fread(fid, 1,'short');
% MeasHISTInfo  HISTInfo; // extension of FCSInfo, valid only for FIFO meas
msd.fida_time       = fread(fid, 1,'float');
msd.filda_time      = fread(fid, 1,'float');
msd.fida_points     = fread(fid, 1,'int32');
msd.filda_points    = fread(fid, 1,'int32');
msd.mcs_time        = fread(fid, 1,'float');
msd.mcs_points      = fread(fid, 1,'int32');
msd.cross_calc_phot = fread(fid, 1,'uint32');
msd.mcsta_points    = fread(fid, 1,'ushort');
msd.mcsta_flags     = fread(fid, 1,'ushort');
msd.mcsta_tpp       = fread(fid, 1,'uint32');
msd.calc_markers    = fread(fid, 1,'uint32');
msd.reserved3       = fread(fid, 1,'double');
%MeasHISTInfoExt  HISTInfoExt; // extension of HSTInfo, valid only for FIFO meas
%????
msd.reserve         = fread(fid, 65,'*char')';
display('if_bh_loadsdt> Measuremwent Data Block Decription Loaded (verify last part)');