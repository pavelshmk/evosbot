import hashlib
id = 593899773824729118
print(hashlib.scrypt(id.to_bytes(8, byteorder='little'), salt=b'KL3982872uu2cjiOCz', n=16, r=1, p=1, dklen=16).hex())