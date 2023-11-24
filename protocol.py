from struct import pack


class Protocol:
    def __init__(self) -> None:
        self.type = b''
        self.frag = b''
        self.identifier = b''
        self.checksum = b''
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

        """
        self.identifier = msg[2:5]
        self.checksum = msg[5:8]
        """
        self.data = msg[1:]

    #nastavi typ spravy -> prve 4 bity v hlavicke
    def setType(self, packetType=str) -> None:
        if packetType == "ACK":
            self.type = '0'
            self.setFrag('0')

        elif packetType == "MSG":
            self.type = '1'
        
        elif packetType == "FILENAME":
            self.type = '2'
            self.setFrag('0')
        
        elif packetType == "FILECONTENT":
            self.type = '3'
        
        elif packetType == "ERR":
            self.type = '4'

    def getType(self) -> str:
        return self.type

    #nastavi fragmentaciu spravy -> 5. - 8. bit v hlavicke
    def setFrag(self, frag=str) -> None:
        self.frag = frag

    def getFrag(self):
        return self.frag
    
    
    #prevedie int ID na 2B format 
    def setIdentifier(self, identifier: int) -> None:
        self.identifier = pack('>H', identifier)

    #vrati ID ako int
    def getidentifier(self):
        return (self.identifier.hex(), 16)
    
    


    def setCheckSum() -> None:
        pass

    
    
    def getChecksum(self):
        return self.checksum
    

    #zakoduje data(string) do utf-8 formate
    def setData(self, string=str) -> None:
        self.data = string.encode("utf-8")
    
    #odkoduje data a vrati ich ako string
    def getData(self):
        return self.data.decode("utf-8")
    

    #vrati hlavicku + data
    def getFullPacket(self):
        return bytes.fromhex(self.type + self.frag) + self.data

