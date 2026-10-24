"""Supplied unpainted demo regression: visible identity probes, not physical GT."""
import base64,unittest
from pathlib import Path
import cv2,numpy as np
from test_console import server
from packing_vision import segment_cardboard

class PlainCardboardRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.results={name:segment_cardboard((root/'app/static/photos'/name).read_bytes()) for name in ['flat-brown-three.png','flat-brown-five.png']}
    def labels(self,name):
        result=self.results[name]
        self.assertIn('OPENCV5_DNN_EFFICIENTSAM',result['algorithm'])
        self.assertFalse(result['physical_action_authorized'])
        return cv2.imdecode(np.frombuffer(base64.b64decode(result['labels_png'].split(',')[1]),np.uint8),0)
    def test_three_plain_sheets_keep_front_flaps_with_the_front_body(self):
        result=self.results['flat-brown-three.png'];self.assertEqual(len(result['regions']),3)
        labels=self.labels('flat-brown-three.png')
        identities=[int(labels[y,x]) for x,y in [(200,280),(650,200),(550,450)]]
        self.assertEqual(len(set(identities)),3);self.assertNotIn(0,identities)
        for x,y in [(300,380),(800,500),(600,300)]:self.assertEqual(labels[y,x],identities[2])
        self.assertEqual(labels[10,10],0)
    def test_five_plain_sheets_do_not_split_the_front_fold_lines_into_objects(self):
        result=self.results['flat-brown-five.png'];self.assertEqual(len(result['regions']),5)
        labels=self.labels('flat-brown-five.png')
        identities=[int(labels[y,x]) for x,y in [(320,180),(740,220),(150,400),(800,480),(500,470)]]
        self.assertEqual(len(set(identities)),5);self.assertNotIn(0,identities)
        for x,y in [(220,500),(520,620),(480,380)]:self.assertEqual(labels[y,x],identities[-1])
