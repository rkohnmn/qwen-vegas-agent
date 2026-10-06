// Untested draft copied verbatim from docs/VEGAS_NOTES.md Section 10. Do not run on real projects.
using System;
using System.Text;
using System.Windows.Forms;
using ScriptPortal.Vegas;

public class EntryPoint
{
    public void FromVegas(Vegas vegas)
    {
        try
        {
            // Find the text generator by name fragment; the exact name varies by version (pitfall P12).
            PlugInNode textPlug = null;
            foreach (PlugInNode n in vegas.Generators)
            {
                if (n.Name != null && n.Name.IndexOf("Titles", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    textPlug = n;
                    break;
                }
            }
            if (textPlug == null) { MessageBox.Show("No Titles generator found"); return; }

            Media media = new Media(textPlug);

            // Place one text event on the first video track at 0 for 2 seconds.
            VideoTrack vt = null;
            foreach (Track t in vegas.Project.Tracks)
            {
                if (t.IsVideo()) { vt = (VideoTrack)t; break; }
            }
            if (vt == null) { MessageBox.Show("Need at least one video track"); return; }

            using (UndoBlock undo = new UndoBlock("TextProbe"))
            {
                VideoEvent ev = vt.AddVideoEvent(Timecode.FromMilliseconds(0), Timecode.FromMilliseconds(2000));
                ev.AddTake(media.GetVideoStreamByIndex(0));

                // Dump parameters of the generator effect. Member names are unverified.
                StringBuilder sb = new StringBuilder();
                sb.AppendLine("Generator: " + textPlug.Name + "  UID=" + textPlug.UniqueID);
                Effect gen = media.Generator;
                OFXEffect ofx = gen.OFXEffect;
                foreach (OFXParameter p in ofx.Parameters)
                {
                    sb.AppendLine(p.Name + "  |  " + p.GetType().Name);
                }
                MessageBox.Show(sb.ToString());
            }
        }
        catch (Exception e)
        {
            MessageBox.Show("TextProbe failed: " + e.ToString());
        }
    }
}
