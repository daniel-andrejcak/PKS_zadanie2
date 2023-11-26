from struct import pack


class Protocol:
    def __init__(self) -> None:
        self.type = '\x00'
        self.frag = ''
        self.identifier = b'\x00\x00'
        self.checksum = b'\x00\x00'
        self.data = b''


    #constructor pre vytvorenie objektu na strane prijimaca
    def buildFromBytes(self, msg) -> None:
        temp = hex(int.from_bytes(msg[:1]))[2:]

        if temp == '0':
            self.type = '0'
            self.frag = '0'
        else:
            self.type = temp[0]
            self.frag = temp[1]

        self.identifier = msg[1:3]
        self.checksum = msg[3:5]

        self.data = msg[5:]



    #nastavi typ spravy -> prve 4 bity v hlavicke
    def setType(self, packetType=str) -> None:
        if packetType == "ACK":
            self.type = '0'
        
        elif packetType == "MSG":
            self.type = '1'
        
        elif packetType == "FILENAME":
            self.type = '2'
        
        elif packetType == "FILECONTENT":
            self.type = '3'

        elif packetType == "CLOSE":
            self.type = '4'

        elif packetType == "SWITCH":
            self.type = '5'
        
        elif packetType == "REMAIN CONNECTION":
            self.type = '6'
        
        elif packetType == "ERR":
            self.type = '7'

        self.setFrag("NO")
    
    def getType(self) -> str:
        if self.type == '0':
            return "ACK"
        elif self.type == '1':
            return "MSG"
        elif self.type == '2':
            return "FILENAME"
        elif self.type == '3':
            return "FILECONTENT"
        elif self.type == '4':
            return "CLOSE"
        elif self.type == '5':
            return "SWITCH"
        elif self.type == '6':
            return "REMAIN CONNECTION"
        elif self.type == '7':
            return "ERR"

        return self.type

    #nastavi fragmentaciu spravy -> 5. - 8. bit v hlavicke
    def setFrag(self, frag=str) -> None:
        if frag == "NO":
            self.frag = '0'
        elif frag == "FIRST":
            self.frag = '1'
        elif frag == "MORE":
            self.frag = '2'
        elif frag == "LAST":
            self.frag = '3'

    def getFrag(self):
        if self.frag == '0':
            return "NO"
        elif self.frag == '1':
            return "FIRST"
        elif self.frag == '2':
            return "MORE"
        elif self.frag == '3':
            return "LAST"
    
    
    #prevedie int ID na 2B format 
    def setIdentifier(self, identifier: int) -> None:
        self.identifier = pack('>H', identifier)

    #vrati ID ako int
    def getIdentifier(self):
        return int(self.identifier.hex(), 16)
    

    def setChecksum(self) -> None:
        divisor=0x11021
        word = int.from_bytes(self.data, byteorder='big')
        word <<= 16

        while word.bit_length() > 16:

            if word.bit_length() > divisor.bit_length():
                divisor <<= (word.bit_length() - divisor.bit_length())
            else:
                divisor >>= (divisor.bit_length() - word.bit_length())

            word ^= divisor

        self.checksum = pack('>H', word)

    
    
    def getChecksum(self):
        return self.checksum
    

    #zakoduje data(string) do utf-8 formate
    def setData(self, string=str) -> None:
        self.data = string.encode("utf-8")
        self.setChecksum()

    
    #odkoduje data a vrati ich ako string
    def getData(self):
        return self.data.decode("utf-8")
    

    #vrati hlavicku + data
    def getFullPacket(self):
        return bytes.fromhex(self.type + self.frag) + self.identifier + self.checksum + self.data

