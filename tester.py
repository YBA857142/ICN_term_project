import sys

if __name__ == "__main__":
  bin = open(sys.argv[1], 'rb')
  bstr = bin.read()
  print(bstr.decode('utf-8'))