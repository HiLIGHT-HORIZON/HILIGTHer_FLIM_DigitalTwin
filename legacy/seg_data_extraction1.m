function [macrotime routing mark gap mtov invalid utime seg_checker remainder seg_overflow] = seg_data_extraction1(seg_A)

% Becker&Hickl file format specification
%
%           Bit7    Bit6    Bit5    Bit4    Bit3    Bit2    Bit1    Bit0
% Byte 0    MT[7]   MT[6]   MT[5]   MT[4]   MT[3]   MT[2]   MT[1]   MT[0]
% Byte 1    ROUT[3] ROUT[2] ROUT[1] ROUT[0] MT[11]  MT[10]  MT[9]   MT[8]
% Byte 2    ADC[7]  ADC[6]  ADC[5]  ADC[4]  ADC[3]  ADC[2]  ADC[1]  ADC[0]
% Byte 3    INVALID MTOV    GAP     MARK    ADC[11] ADC[10] ADC[9]  ADC[8]

% Reading 16 bits words:
%
%       bit:0   1   2   3   4   5   6   7   8   9   10   11   12 13 14  15      
% Word 1    MT0 MT1 MT2 MT3 MT4 MT5 MT6 MT7 MT8 MT9 MT10 MT11 R0 R1 R2  R3       
% Word 2    A0  A1  A2  A3  A4  A5  A6  A7  A8  A9  A10  A11  mk gp mtv inv
%
% MTOV of mtv is MicroTime Overlflow
% MT is MicroTime
% MARK or MK flagging marking pulses (as pixel clock)
%
% To select macro- and micro- times mask bits of word1 and 2 with 4095 (first 11 bits)
% Routing signals in word1 masked with 61440 and then deviding by 2^12
% 

    block_size = 50000;
    
    data = seg_A';
    
    % get  last four bits of the word 2, including mk () gp mtv inv
    seg_checker = cast(bitand(data(:,2), 61440), 'double');
    
    % Macrotime, select the first 12 bits for macrotime specification
    macrotime = cast(bitand(data(:,1), 4095), 'double');    
    % Routing, select the last 4 bits for the routing signal specification
    routing   = cast(bitand(data(:,1), 61440),'double')/2^12;
    % MARK, GAP, MTOV and INVALID, 13th to 16th  bits of second word
    mark      = bitand(data(:,2), 4096)/4096;
    gap       = bitand(data(:,2), 8192)/8192;
    mtov      = bitand(data(:,2), 16384)/16384;
    invalid   = bitand(data(:,2), 32768)/32768;
    
    utime = cast(4095 - bitand(data(:,2), 4095), 'double');
    
    if (length(data) == block_size);        
        seg_overflow = zeros(block_size,1);
    
        %check INVALID&MTOV
        x = find(seg_checker == 49152);
        seg_overflow(x) = macrotime(x);    
               
        %check INVALID
        y = find(seg_checker == 16384);
        seg_overflow(y) = 1;
     
        remainder = 0;    
    else
        seg_overflow = zeros(length(data),1);
    
        x = find(seg_checker == 49152);
        seg_overflow(x) = macrotime(x);           
        
        y = find(seg_checker == 16384);
        seg_overflow(y) = 1;       
    
        remainder = block_size - length(data);     
    end
end