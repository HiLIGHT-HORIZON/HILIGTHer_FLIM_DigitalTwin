function header_ascii = if_bh_parseinfo(fid,inf_off)
header_ascii={};
% READ INFORMATION BLOCK
fseek(fid,inf_off,'bof');
for i=1:100 % maximum lines parsed if an end of block is not identified
    header_ascii{i} = fgetl(fid);
    if ~isempty(strfind(header_ascii{i},'*END'))
        display('if_bh_loadsdt> ASCII header read');
        break
    end
end