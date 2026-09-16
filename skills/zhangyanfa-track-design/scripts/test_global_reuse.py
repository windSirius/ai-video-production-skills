import unittest
from audit_global_reuse import audit

def seg(i,fam,src='one',a=0,b=2):return dict(segment_id=str(i),cue_id=i,visual_family_id=fam,source_id=src,source_in=a,source_out=b,start_frame=(i-1)*120,end_frame=i*120)

class ReuseContract(unittest.TestCase):
 def test_nonadjacent_replays_are_counted(self):
  x=[seg(1,'f'),seg(2,'g',a=8,b=10),seg(3,'f')]
  self.assertEqual(audit(x)['repeated_group_count'],1)
 def test_cropped_renamed_and_cross_source_exports_do_not_escape(self):
  x=[seg(1,'original','one',10,12),seg(2,'other','two',0,2),seg(3,'new_crop_id','export',0,2)]
  origin={'one':{'parent_sha256':'real','offset_s':0},'export':{'parent_sha256':'real','offset_s':10}}
  r=audit(x,origin);self.assertEqual(r['repeated_group_count'],1);self.assertEqual(r['extra_occurrences'],1)
 def test_more_than_four_groups_fails_even_when_not_adjacent(self):
  x=[seg(i+1,str(i%5),a=(i%5)*5,b=(i%5)*5+2) for i in range(10)]
  self.assertEqual(audit(x)['status'],'fail')
 def test_distinct_original_ranges_and_families_can_pass(self):
  self.assertEqual(audit([seg(1,'a',a=20,b=22),seg(2,'b',a=4,b=6)])['status'],'pass')
 def test_adjacent_replay_cannot_pass_by_low_global_count(self):
  self.assertEqual(audit([seg(1,'a'),seg(2,'a')])['status'],'fail')
 def test_one_group_replayed_three_times_fails(self):
  x=[seg(1,'a'),seg(2,'b',a=4,b=6),seg(3,'a'),seg(4,'c',a=8,b=10),seg(5,'a')]
  result=audit(x)
  self.assertEqual(result['repeated_group_count'],1)
  self.assertEqual(result['max_group_occurrences'],3)
  self.assertEqual(result['status'],'fail')
 def test_empty_or_duplicate_segments_cannot_pass(self):
  with self.assertRaises(ValueError):audit([])
  with self.assertRaises(ValueError):audit([seg(1,'a'),seg(1,'b',a=4,b=6)])
if __name__=='__main__':unittest.main()
