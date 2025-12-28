function [mt rt ut mk gp mv in seg_checker remainder of] = if_bh_parse_fifoimagestream(data, block_size)

%@@@@@@@ tyring to remove seg_checked and remainder


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
% Word 2    A0  A1  A2  A3  A4  A5  A6  A7  A8  A9  A10  A11  mk gp mv  in
%
% 
% MT0-MT11, macrotime (when an event occurs), 12 bits, then stored in "mt"
% ADC or A 0-11, adc value or microtime when appropriate, 12 bits, then stored in "ut"
% ROUT or R 0-3, 4 routing bits, then stored in "rt"
% INVALID or "in" invalid photon bit
% MTOV or "mv" macrotime overflow bit
% GAP or "gp" gap bit
% MARK or "mk" marking pulse bit (e.g., pixel clock)
%

% NOTE: cast is used to return a decimal value from the selected bits. Also but2dec/dec2bit could be used but cast/bitand
% appear to be more efficient. Bitand is used to mask the relevent bits. For instance, MicroTimes are in the first 12 bits of
% the first 16 bits word stored in "data". In order to select the first 12 bits, bitand is used with the value 4095 (first 12
% bit set to 1, remaining to 0). The resulting bits are then cadsted to the typle double.
%

%
% To select macro- and micro- times mask bits of word1 and 2 with 4095 (first 11 bits)
% Routing signals in word1 masked with 61440 and then deviding by 2^12
% 


    % initialize overflows and remainder variables
    if (length(data) == block_size);        
        of = zeros(block_size,1);
        remainder = 0;    
    else
        of = zeros(length(data),1);
        remainder = block_size - length(data);     
    end
    
    % get  last four bits of the word 2, including mk () gp mtv inv
    % @@@ trying to remove the next variable
    seg_checker = cast(bitand(data(:,2), 61440), 'double');
    
    
    % Parsing first word
    mt = cast(bitand(data(:,1), 4095), 'double');        % Macrotime, select the first 12 bits for macrotime specification    
    rt = cast(bitand(data(:,1), 61440),'double')/2^12;   % Routing, select the last 4 bits for the routing signal specification. Division by 2^12 needed
    
    % Parsing second word
    mk = bitand(data(:,2), 4096)/4096;                   % Mark bit
    gp = bitand(data(:,2), 8192)/8192;                   % Gap bit
    mv = bitand(data(:,2), 16384)/16384;                 % MTOV bit
    in = bitand(data(:,2), 32768)/32768;                 % Invalid bit
    ut = cast(4095 - bitand(data(:,2), 4095), 'double'); % Microtime value
    
    %check INVALID&MTOV
    x = find(mv==1 & in==1);
    of(x) = mt(x);    

    %check INVALID    @@@@ double check this line!!! it is actually checling the overflows
    y = find(mv==1);
    of(y) = 1;
