const { encrypt } = require('eciesjs');
const pub = '04fba314bf9c206288e1d8d54bc0c21aa4d5cda72eb77647febd65e12e9235536daa655ead1a399d7bdb3f76bad55450e7b76192cf3ee99bcfbd275004a9004416';
const plain = JSON.stringify({ name: 'Test User', dob: '1990-01-01' });
const ct = encrypt(pub, Buffer.from(plain));
const fs = require('fs');
fs.writeFileSync('test_ct.hex', ct.toString('hex'));
console.log('wrote', ct.length, 'bytes to test_ct.hex');
