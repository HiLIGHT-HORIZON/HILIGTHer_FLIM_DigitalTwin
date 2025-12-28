
clear all;
clc;


file_name = 'ttt_m2_002.spc';
file_path = 'C:\Users\Virgilio Leon Lew\Desktop\SPC\';

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
    
        clear A;

%%restart the fread function

frewind(fid); 


block_size = 50000;
rp = 1;

img = zeros(256);

%read header info
        A = fread(fid, [4,1], '*uint8');   

clear('A','h1');

%begin block processing

            while (rp<N);
                
              seg_A = fread(fid, [2, block_size], '*uint16');
              
              [seg_macrotime seg_routing seg_mark seg_gap seg_mtov seg_invalid seg_utime seg_checker remainder seg_overflow] = seg_data_extraction1(seg_A);
                        
              
              100*rp/N
              
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
   
            end
            
    

    
    
    % identify line trigger by MARK=1 and RT[1]=1, pixel with RT[0]=1,
    % frame with RT[2]=1... attention, in the latter case it appears also
    % pxl high
    %lin_pos = find(routing==2&mark==1);
    %pxl_pos = find(routing==1&mark==1);
    %frm_pos = find(routing==6&mark==1);
    
    % for mark specification bit 11 and 0 of word 2 are invalid
    % therfore mask with 2^11-1=2047 and devide by 2
    %pxl_val = cast(bitand(data(pxl_pos,2),2^8-1),'double');
    %lin_val = cast(bitand(data(lin_pos,2),2^8-1),'double');
    %pxl_val = bitand(4095-utime(pxl_pos),2^8-1);
    %lin_val = bitand(4095-utime(lin_pos),2^8-1);
    
              %pht_pos = find(mark==0 & invalid==0);
%               in = length(pht_pos);
%               for ip=1:in
%                 x = pxl_val(max(find(pxl_pos<pht_pos(ip))))+1;
%                 y = lin_val(max(find(lin_pos<pht_pos(ip))))+1;
%                 img(x,y) = img(x,y) + 100;  
%                 ip/in
%               end    
%     
%%    
tic
img = zeros(300);
x=1;y=1;
in=length(utime);
for ip=1:in
   if mark(ip)==1
       if routing(ip)==1 % pixel
            %x = bitand(4095-utime(ip),2^8-1)+1;
            x=x+1;
       elseif routing(ip)==2 %line
            y=y+1;
            x=1;
       elseif routing(ip)==6 %frame
           x=1;
           y=1;
       end
   else
    if ~invalid(ip)
        img(x,y)=img(x,y)+1;      
    end
   end
     %ip/in
end
toc

figure,imagesc(img)
set(gca,'clim',[min(img(:)) 5*mean(img(:))])


return
%%
    
    overflow_cumulative = cumsum(overflow);
    clear overflow;
    macrotime = macrotime + (overflow_cumulative * 4096);        
   %find invalid photons    
    
            set = [49152 32768]; 
            n = find(ismember(checker, set));
            

            macrotime(n) = [];
            utime(n) = [];
            
                       
   %clear('N','block_size','checker','fid', 'n','set','remainder', 'rp', 'filename','full_filename');
   clear('-regexp', '|^over|^seg|');

return
%%
figure,plot(cumsum(routing(find(mark==1))==1))
hold on
line=cumsum(routing(find(mark==1))==2);
frame=cumsum(routing(find(mark==1))==6);
plot((line)*256,'r')
plot(frame*256*256,'k')