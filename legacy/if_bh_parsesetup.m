function s = if_bh_parsesetup(fid,set_off)    
    
    fseek(fid,set_off,'bof');

    header_lines = 0;
    s = struct('parameter',{},'type',{},'value',{});    
    
    c = 1; % safety counter, if no endo of block if found
    
    %@@@ not parsing correctly windows parameter for the time being
    
    while 1 % search for parameters within the header
        line = fgetl(fid);
        
       
        if ~isempty(strfind(line,'*END'))
            header_lines = header_lines +2;
            break
        elseif ~isempty(strfind(line,'*BLOCK 1'))
            header_lines = header_lines +1;
            break
        end         
        
        header_lines = header_lines+1;
        
        s_ini = strfind(line,'[');
        s_end = strfind(line,',');
        s_ini2 = strfind(line,',');
        s_end2 = strfind(line,']');
        
        if ~isempty(s_ini) | ~isempty(s_end) | ~isempty(s_ini2) | ~isempty(s_end2)
            s(header_lines).parameter = line(s_ini+1:s_end(1)-1);
            s(header_lines).type  = line(s_end+1:s_ini2(length(s_ini2))-1);
            s(header_lines).value = line(s_ini2(length(s_ini2))+1:s_end2-1);;
        end
        
        if c>10000
            display('if_bh_parsesetup> WARNING: no setup end of block found')
            break
        end
        c = c + 1;
    end  
    display('if_bh_parsesetup> SETUP BLOCK READ');